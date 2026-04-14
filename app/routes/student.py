# app/routes/student.py
"""
Blueprint do Aluno — /student

Rotas HTML:
    GET  /student/schedule            → Grade de horários disponíveis
    GET  /student/bookings            → Próximos agendamentos + recorrentes
    GET  /student/bookings/history    → Histórico de aulas

Rotas AJAX / JSON:
    GET  /student/api/slots           → Slots por data+filtros (recarrega cards)
    POST /student/book/<slot_id>      → Agendar avulso
    GET  /student/book/<slot_id>/alternatives → Sugestões de alternativos
    POST /student/recurring/preview   → Preview de ocorrências (sem gravar)
    POST /student/recurring/create    → Criar série recorrente
    POST /student/booking/<id>/cancel → Cancelar agendamento
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, time
from functools import wraps
from typing import Optional

from flask import Blueprint, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models.booking import Booking, BookingStatus
from app.models.modality import Modality
from app.models.recurring_booking import RecurringBooking, RecurringFrequency
from app.models.schedule_slot import ScheduleSlot
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.scheduling import (
    create_recurring_bookings,
    suggest_alternatives,
    validate_booking,
)

student_bp = Blueprint(
    "student", __name__,
    url_prefix="/student",
    template_folder="../templates",
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_WEEKDAY_BR_SHORT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_WEEKDAY_BR_LONG  = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_DATE_STRIP_DAYS  = 14   # quantos dias exibir na barra de datas
_MAX_FUTURE_BOOK  = 30   # janela padrão de agendamento futuro


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_student(fn):
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)
    return wrapper


def _get_policy(provider) -> dict:
    """Retorna a política do prestador com defaults."""
    defaults = {"min_notice_hours": 2, "cancel_deadline_hours": 4, "max_future_days": 30}
    if provider and provider.schedule_policy_json:
        return {**defaults, **provider.schedule_policy_json}
    return defaults


def _next_weekday_from(from_date: date, weekday: int) -> date:
    days_ahead = (weekday - from_date.weekday()) % 7
    return from_date + timedelta(days=days_ahead)


def _parse_date(s: str) -> date:
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _parse_time(s: str) -> time:
    return datetime.strptime(s[:5], "%H:%M").time()


def _slot_status_label(slot: ScheduleSlot, booked_slot_ids: set) -> str:
    """
    Retorna o estado de UI do slot para o aluno atual:
        'booked'    — já agendado pelo aluno
        'available' — tem vagas
        'few'       — últimas 2 vagas (ou ≤ 20 %)
        'full'      — lotado
        'cancelled' — cancelado
    """
    if slot.status == "cancelled":
        return "cancelled"
    if slot.id in booked_slot_ids:
        return "booked"
    spots = slot.available_spots
    if spots <= 0:
        return "full"
    if spots <= 2 or slot.occupancy_pct >= 80:
        return "few"
    return "available"


def _active_subscriptions() -> list:
    """Retorna assinaturas ativas do usuário logado."""
    return (
        Subscription.query
        .filter_by(user_id=current_user.id, status=SubscriptionStatus.ACTIVE)
        .filter(Subscription.end_date >= date.today())
        .order_by(Subscription.end_date)
        .all()
    )


def _slot_to_dict(slot: ScheduleSlot, booked_slot_ids: set = frozenset()) -> dict:
    return {
        "id": slot.id,
        "date": slot.date.isoformat(),
        "start_time": slot.start_time.strftime("%H:%M"),
        "end_time": slot.end_time.strftime("%H:%M"),
        "max_capacity": slot.max_capacity,
        "booked_count": slot.booked_count,
        "available_spots": slot.available_spots,
        "occupancy_pct": round(slot.occupancy_pct, 1),
        "status": slot.status,
        "ui_status": _slot_status_label(slot, booked_slot_ids),
        "modality_id": slot.modality_id,
        "modality_name": slot.modality.name if slot.modality else None,
        "modality_color": slot.modality.color if slot.modality else "#FF6B35",
        "modality_icon": slot.modality.icon if slot.modality else None,
        "credits_cost": slot.modality.credits_cost if slot.modality else 1,
        "provider_id": slot.provider_id,
        "provider_name": slot.provider.name if slot.provider else "—",
    }


# ---------------------------------------------------------------------------
# GET /student/schedule  — HTML
# ---------------------------------------------------------------------------


@student_bp.route("/schedule")
@_require_student
def schedule():
    # ── Parse query params ──────────────────────────────────────────────
    today = date.today()
    raw_date = request.args.get("date", today.isoformat())
    try:
        selected_date = _parse_date(raw_date)
    except ValueError:
        selected_date = today

    if selected_date < today:
        selected_date = today

    provider_id  = request.args.get("provider_id",  type=int)
    modality_id  = request.args.get("modality_id",  type=int)

    # ── Slots do dia ────────────────────────────────────────────────────
    q = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.date == selected_date,
            ScheduleSlot.status.in_(["active", "full"]),
        )
        .order_by(ScheduleSlot.start_time)
    )
    if provider_id:
        q = q.filter(ScheduleSlot.provider_id == provider_id)
    if modality_id:
        q = q.filter(ScheduleSlot.modality_id == modality_id)

    slots = q.all()

    # ── Bookings do aluno para o dia ────────────────────────────────────
    booked_slot_ids = {
        b.slot_id
        for b in (
            Booking.query
            .join(ScheduleSlot)
            .filter(
                Booking.client_id == current_user.id,
                Booking.status == BookingStatus.CONFIRMED,
                ScheduleSlot.date == selected_date,
            )
            .all()
        )
    }

    # ── Filtros disponíveis ─────────────────────────────────────────────
    providers  = (
        User.query
        .filter(User.role.in_(["instructor", "provider"]), User.is_active == True)
        .order_by(User.name)
        .all()
    )
    modalities = Modality.query.filter_by(is_active=True).order_by(Modality.name).all()

    # ── Date strip (hoje + N dias) ──────────────────────────────────────
    date_range = [today + timedelta(days=i) for i in range(_DATE_STRIP_DAYS)]

    # ── Assinaturas ativas ──────────────────────────────────────────────
    active_subs = _active_subscriptions()

    return render_template(
        "student/schedule.html",
        selected_date=selected_date,
        date_range=date_range,
        slots=slots,
        booked_slot_ids=booked_slot_ids,
        active_subs=active_subs,
        providers=providers,
        modalities=modalities,
        provider_id=provider_id,
        modality_id=modality_id,
        slot_status_label=_slot_status_label,
        today=today,
        weekday_long=_WEEKDAY_BR_LONG,
        weekday_short=_WEEKDAY_BR_SHORT,
    )


# ---------------------------------------------------------------------------
# GET /student/api/slots  — JSON (AJAX: recarrega cards sem reload de página)
# ---------------------------------------------------------------------------


@student_bp.route("/api/slots")
@_require_student
def api_slots():
    today = date.today()
    raw_date = request.args.get("date", today.isoformat())
    try:
        selected_date = _parse_date(raw_date)
    except ValueError:
        return jsonify({"error": "Data inválida."}), 400

    provider_id = request.args.get("provider_id", type=int)
    modality_id = request.args.get("modality_id", type=int)

    q = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.date == selected_date,
            ScheduleSlot.status.in_(["active", "full"]),
        )
        .order_by(ScheduleSlot.start_time)
    )
    if provider_id:
        q = q.filter(ScheduleSlot.provider_id == provider_id)
    if modality_id:
        q = q.filter(ScheduleSlot.modality_id == modality_id)

    slots = q.all()

    booked_slot_ids = {
        b.slot_id
        for b in (
            Booking.query.join(ScheduleSlot)
            .filter(
                Booking.client_id == current_user.id,
                Booking.status == BookingStatus.CONFIRMED,
                ScheduleSlot.date == selected_date,
            )
            .all()
        )
    }

    return jsonify({
        "date": selected_date.isoformat(),
        "weekday": _WEEKDAY_BR_LONG[selected_date.weekday()],
        "slots": [_slot_to_dict(s, booked_slot_ids) for s in slots],
    })


# ---------------------------------------------------------------------------
# POST /student/book/<slot_id>  — AJAX (agendamento avulso)
# ---------------------------------------------------------------------------


@student_bp.route("/book/<int:slot_id>", methods=["POST"])
@_require_student
def book(slot_id: int):
    """
    Fluxo em até 2 cliques:
      - 1 assinatura ativa → clique único (subscription_id enviado automaticamente)
      - N assinaturas     → 2 cliques (seletor + confirmação)
    """
    slot = ScheduleSlot.query.get_or_404(slot_id)
    data = request.get_json(force=True) or {}

    # Resolução da assinatura
    sub_id = data.get("subscription_id")
    subscription: Optional[Subscription] = None
    if sub_id:
        subscription = Subscription.query.filter_by(
            id=sub_id, user_id=current_user.id,
        ).first()

    # Validação via serviço
    ok, error = validate_booking(current_user, slot, subscription)
    if not ok:
        return jsonify({"error": error}), 400

    credits_cost = slot.modality.credits_cost if slot.modality else 1

    booking = Booking(
        client_id=current_user.id,
        slot_id=slot.id,
        subscription_id=subscription.id if subscription else None,
        status=BookingStatus.CONFIRMED,
        cost_at_booking=credits_cost,
    )
    db.session.add(booking)

    if subscription and credits_cost > 0:
        subscription.use_credit(credits_cost)

    db.session.commit()

    return jsonify({
        "message": "Agendamento confirmado!",
        "booking_id": booking.id,
        "slot": _slot_to_dict(slot, {slot.id}),
    }), 201


# ---------------------------------------------------------------------------
# GET /student/book/<slot_id>/alternatives  — AJAX
# ---------------------------------------------------------------------------


@student_bp.route("/book/<int:slot_id>/alternatives")
@_require_student
def slot_alternatives(slot_id: int):
    slot = ScheduleSlot.query.get_or_404(slot_id)
    alts = suggest_alternatives(slot)
    booked_ids = {
        b.slot_id
        for b in Booking.query.filter_by(
            client_id=current_user.id, status=BookingStatus.CONFIRMED,
        ).all()
    }
    return jsonify({
        "alternatives": [_slot_to_dict(a, booked_ids) for a in alts],
    })


# ---------------------------------------------------------------------------
# POST /student/recurring/preview  — AJAX (calcula ocorrências, não grava)
# ---------------------------------------------------------------------------


@student_bp.route("/recurring/preview", methods=["POST"])
@_require_student
def recurring_preview():
    """
    Recebe os parâmetros da série recorrente e retorna:
      - available: lista de datas com slot disponível
      - conflicts: lista de datas com motivo (sem slot / sem vaga / já agendado)
    Não grava nada no banco.
    """
    data = request.get_json(force=True) or {}

    try:
        provider_id  = int(data["provider_id"])
        start_time   = _parse_time(data["start_time"])
        weekday      = int(data["weekday"])         # 0=seg … 6=dom
        frequency    = data.get("frequency", "weekly")
        valid_from   = _parse_date(data["valid_from"])
        valid_until  = _parse_date(data["valid_until"]) if data.get("valid_until") else None
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"Parâmetro inválido: {exc}"}), 400

    today    = date.today()
    start    = max(valid_from, today)
    step     = 7 if frequency == "weekly" else 14
    cutoff   = today + timedelta(days=730)
    current  = _next_weekday_from(start, weekday)

    available: list[str] = []
    conflicts: list[dict] = []

    while (valid_until is None or current <= valid_until) and current <= cutoff:
        slot = (
            ScheduleSlot.query
            .filter_by(
                provider_id=provider_id,
                date=current,
                start_time=start_time,
                status="active",
            )
            .first()
        )

        if not slot:
            conflicts.append({"date": current.isoformat(), "reason": "Sem horário disponível"})
        elif slot.available_spots <= 0:
            conflicts.append({"date": current.isoformat(), "reason": "Sem vagas"})
        else:
            already = Booking.query.filter_by(
                client_id=current_user.id,
                slot_id=slot.id,
                status=BookingStatus.CONFIRMED,
            ).first()
            if already:
                conflicts.append({"date": current.isoformat(), "reason": "Já agendado"})
            else:
                available.append(current.isoformat())

        current += timedelta(days=step)

    return jsonify({
        "available": available,
        "conflicts": conflicts,
        "total_available": len(available),
        "total_conflicts": len(conflicts),
    })


# ---------------------------------------------------------------------------
# POST /student/recurring/create  — cria série recorrente
# ---------------------------------------------------------------------------


@student_bp.route("/recurring/create", methods=["POST"])
@_require_student
def recurring_create():
    """
    Persiste RecurringBooking + todos os Bookings individuais disponíveis.
    Retorna lista dos criados e dos conflitos.
    """
    data = request.get_json(force=True) or {}

    try:
        provider_id  = int(data["provider_id"])
        modality_id  = data.get("modality_id")
        start_time   = _parse_time(data["start_time"])
        weekday      = int(data["weekday"])
        frequency    = data.get("frequency", "weekly")
        valid_from   = _parse_date(data["valid_from"])
        valid_until  = _parse_date(data["valid_until"]) if data.get("valid_until") else None
        sub_id       = data.get("subscription_id")
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"Parâmetro inválido: {exc}"}), 400

    subscription: Optional[Subscription] = None
    if sub_id:
        subscription = Subscription.query.filter_by(
            id=sub_id, user_id=current_user.id,
        ).first()

    freq_enum = (
        RecurringFrequency.WEEKLY
        if frequency == "weekly"
        else RecurringFrequency.BIWEEKLY
    )

    recurring = RecurringBooking(
        client_id=current_user.id,
        provider_id=provider_id,
        modality_id=modality_id or None,
        weekday=weekday,
        start_time=start_time,
        frequency=freq_enum,
        subscription_id=subscription.id if subscription else None,
        valid_from=valid_from,
        valid_until=valid_until,
        is_active=True,
    )
    db.session.add(recurring)
    db.session.flush()   # garante recurring.id

    created, conflicts = create_recurring_bookings(recurring, subscription)
    db.session.commit()

    return jsonify({
        "recurring_id": recurring.id,
        "created": len(created),
        "conflicts": [c.isoformat() for c in conflicts],
        "message": (
            f"{len(created)} aula(s) agendada(s)."
            + (f" {len(conflicts)} data(s) indisponível(is)." if conflicts else "")
        ),
    }), 201


# ---------------------------------------------------------------------------
# POST /student/booking/<id>/cancel  — AJAX
# ---------------------------------------------------------------------------


@student_bp.route("/booking/<int:booking_id>/cancel", methods=["POST"])
@_require_student
def booking_cancel(booking_id: int):
    booking = Booking.query.filter_by(
        id=booking_id, client_id=current_user.id,
    ).first_or_404()

    if booking.status != BookingStatus.CONFIRMED:
        return jsonify({"error": "Este agendamento não pode ser cancelado."}), 400

    # ── Verificar prazo de cancelamento ─────────────────────────────────
    slot = booking.slot
    policy = _get_policy(slot.provider if slot else None)
    deadline_hours: int = policy.get("cancel_deadline_hours", 4)

    slot_dt = datetime.combine(slot.date, slot.start_time)
    if datetime.utcnow() + timedelta(hours=deadline_hours) > slot_dt:
        return jsonify({
            "error": (
                f"Prazo de cancelamento encerrado. "
                f"É necessário cancelar com pelo menos {deadline_hours}h de antecedência."
            ),
            "deadline_hours": deadline_hours,
        }), 409

    data = request.get_json(force=True) or {}
    reason = data.get("reason", "Cancelado pelo aluno.")

    booking.status      = BookingStatus.CANCELLED
    booking.cancelled_at = datetime.utcnow()
    booking.cancel_reason = reason

    # ── Estornar créditos ────────────────────────────────────────────────
    if booking.subscription_id and booking.cost_at_booking > 0:
        sub = Subscription.query.get(booking.subscription_id)
        if sub:
            sub.refund_credit(booking.cost_at_booking)

    db.session.commit()

    return jsonify({
        "message": "Agendamento cancelado. Créditos estornados.",
        "booking_id": booking.id,
        "credits_refunded": booking.cost_at_booking,
    })


# ---------------------------------------------------------------------------
# GET /student/bookings  — HTML
# ---------------------------------------------------------------------------


@student_bp.route("/bookings")
@_require_student
def bookings():
    today = date.today()

    # Próximos agendamentos
    upcoming = (
        Booking.query
        .join(ScheduleSlot)
        .filter(
            Booking.client_id == current_user.id,
            Booking.status == BookingStatus.CONFIRMED,
            ScheduleSlot.date >= today,
        )
        .order_by(ScheduleSlot.date, ScheduleSlot.start_time)
        .all()
    )

    # Recorrentes ativos
    active_recurring = (
        RecurringBooking.query
        .filter_by(client_id=current_user.id, is_active=True)
        .all()
    )

    # Política de cancelamento por booking (para exibir deadline no template)
    def _can_cancel(b: Booking) -> tuple[bool, int]:
        policy = _get_policy(b.slot.provider if b.slot else None)
        dh = policy.get("cancel_deadline_hours", 4)
        slot_dt = datetime.combine(b.slot.date, b.slot.start_time)
        return datetime.utcnow() + timedelta(hours=dh) < slot_dt, dh

    cancel_info = {b.id: _can_cancel(b) for b in upcoming}

    return render_template(
        "student/bookings.html",
        upcoming=upcoming,
        active_recurring=active_recurring,
        cancel_info=cancel_info,
        today=today,
        weekday_long=_WEEKDAY_BR_LONG,
        weekday_short=_WEEKDAY_BR_SHORT,
    )


# ---------------------------------------------------------------------------
# POST /student/recurring/<id>/stop  — AJAX (desativa série)
# ---------------------------------------------------------------------------


@student_bp.route("/recurring/<int:rec_id>/stop", methods=["POST"])
@_require_student
def recurring_stop(rec_id: int):
    rec = RecurringBooking.query.filter_by(
        id=rec_id, client_id=current_user.id,
    ).first_or_404()
    rec.is_active = False
    db.session.commit()
    return jsonify({"message": "Série recorrente encerrada.", "recurring_id": rec_id})


# ---------------------------------------------------------------------------
# GET /student/bookings/history  — HTML (tab inside bookings)
# ---------------------------------------------------------------------------


@student_bp.route("/bookings/history")
@_require_student
def bookings_history():
    past = (
        Booking.query
        .join(ScheduleSlot)
        .filter(
            Booking.client_id == current_user.id,
            Booking.status.in_([
                BookingStatus.COMPLETED,
                BookingStatus.NO_SHOW,
                BookingStatus.CANCELLED,
            ]),
        )
        .order_by(ScheduleSlot.date.desc(), ScheduleSlot.start_time.desc())
        .limit(60)
        .all()
    )

    return render_template(
        "student/history.html",
        past=past,
        weekday_short=_WEEKDAY_BR_SHORT,
    )
