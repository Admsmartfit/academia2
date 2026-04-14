# app/routes/provider.py
"""
Blueprint do Prestador — /provider

Rotas HTML (renderizam template):
    GET  /provider/dashboard
    GET  /provider/calendar
    GET  /provider/templates

Rotas AJAX / API JSON:
    GET  /provider/api/calendar-events          ← FullCalendar feed
    POST /provider/calendar/slot/create
    POST /provider/calendar/slot/<id>/delete
    POST /provider/templates/create
    POST /provider/templates/<id>/edit
    POST /provider/templates/<id>/delete
    GET  /provider/slot/<id>/attendees
    POST /provider/slot/<id>/cancel
    POST /provider/slot/<id>/update-capacity
    POST /provider/day/<date>/block
    POST /provider/checkin/<booking_id>
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from functools import wraps

from flask import Blueprint, abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app import db
from app.models.booking import Booking, BookingStatus
from app.models.modality import Modality
from app.models.schedule_slot import ScheduleSlot
from app.models.schedule_template import ScheduleTemplate
from app.services.scheduling import (
    generate_slots_from_template,
)

provider_bp = Blueprint(
    "provider", __name__,
    url_prefix="/provider",
    template_folder="../templates",
)

# ---------------------------------------------------------------------------
# Decorador de autorização
# ---------------------------------------------------------------------------


def _require_provider(fn):
    """Garante que o usuário logado é instructor/provider."""
    @wraps(fn)
    @login_required
    def wrapper(*args, **kwargs):
        if not current_user.is_instructor:
            abort(403)
        return fn(*args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _slot_color_key(slot: ScheduleSlot) -> str:
    """
    Retorna a chave de cor por ocupação (PRD § 3.2 + task spec):
        gray    — sem inscritos
        green   — < 50 %
        yellow  — 50 – 80 %
        red     — > 80 %
        cancelled — slot cancelado
    """
    if slot.status == "cancelled":
        return "cancelled"
    pct = slot.occupancy_pct
    if pct == 0:
        return "gray"
    if pct < 50:
        return "green"
    if pct <= 80:
        return "yellow"
    return "red"


_COLOR_MAP = {
    "gray":      "#adb5bd",
    "green":     "#28a745",
    "yellow":    "#e0a800",
    "red":       "#dc3545",
    "cancelled": "#6c757d",
}


def _slot_to_event(slot: ScheduleSlot) -> dict:
    """Serializa um ScheduleSlot para o formato de evento do FullCalendar."""
    color_key = _slot_color_key(slot)
    title_parts = [slot.start_time.strftime("%H:%M")]
    if slot.modality:
        title_parts.append(slot.modality.name)
    title_parts.append(f"{slot.booked_count}/{slot.max_capacity}")

    event: dict = {
        "id": str(slot.id),
        "title": "  ".join(title_parts),
        "start": f"{slot.date.isoformat()}T{slot.start_time.strftime('%H:%M:%S')}",
        "end": f"{slot.date.isoformat()}T{slot.end_time.strftime('%H:%M:%S')}",
        "backgroundColor": _COLOR_MAP[color_key],
        "borderColor": _COLOR_MAP[color_key],
        "textColor": "#fff" if color_key != "yellow" else "#212529",
        "classNames": [f"slot-{color_key}"],
        "extendedProps": {
            "slot_id": slot.id,
            "status": slot.status,
            "booked_count": slot.booked_count,
            "max_capacity": slot.max_capacity,
            "available_spots": slot.available_spots,
            "occupancy_pct": round(slot.occupancy_pct, 1),
            "modality_name": slot.modality.name if slot.modality else None,
            "modality_color": slot.modality.color if slot.modality else "#FF6B35",
            "cancel_reason": slot.cancel_reason,
            "color_key": color_key,
        },
    }
    # Slots cancelados ficam com texto riscado via CSS class
    if color_key == "cancelled":
        event["classNames"].append("slot-cancelled")
    return event


def _slot_to_dict(slot: ScheduleSlot) -> dict:
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
        "color_key": _slot_color_key(slot),
        "modality_id": slot.modality_id,
        "modality_name": slot.modality.name if slot.modality else None,
        "modality_color": slot.modality.color if slot.modality else "#FF6B35",
        "cancel_reason": slot.cancel_reason,
        "template_id": slot.template_id,
    }


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# GET /provider/dashboard  — HTML
# ---------------------------------------------------------------------------


@provider_bp.route("/dashboard")
@_require_provider
def dashboard():
    today = date.today()
    slots = (
        ScheduleSlot.query
        .filter_by(provider_id=current_user.id, date=today)
        .order_by(ScheduleSlot.start_time)
        .all()
    )
    total_booked = sum(s.booked_count for s in slots)
    total_capacity = sum(s.max_capacity for s in slots)

    return render_template(
        "provider/dashboard.html",
        today=today,
        slots=slots,
        total_booked=total_booked,
        total_capacity=total_capacity,
        slot_color_key=_slot_color_key,
    )


# ---------------------------------------------------------------------------
# GET /provider/calendar  — HTML
# ---------------------------------------------------------------------------


@provider_bp.route("/calendar")
@_require_provider
def calendar():
    modalities = Modality.query.filter_by(is_active=True).order_by(Modality.name).all()
    return render_template("provider/calendar.html", modalities=modalities)


# ---------------------------------------------------------------------------
# GET /provider/api/calendar-events  — JSON (FullCalendar feed)
# ---------------------------------------------------------------------------


@provider_bp.route("/api/calendar-events")
@_require_provider
def api_calendar_events():
    """
    FullCalendar chama esta rota com ?start=YYYY-MM-DD&end=YYYY-MM-DD.
    Retorna lista de eventos no formato FullCalendar.
    """
    try:
        start = _parse_date(request.args.get("start", "")[:10])
        end = _parse_date(request.args.get("end", "")[:10])
    except (ValueError, TypeError):
        return jsonify({"error": "Parâmetros start/end inválidos."}), 400

    slots = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.provider_id == current_user.id,
            ScheduleSlot.date >= start,
            ScheduleSlot.date < end,
        )
        .order_by(ScheduleSlot.date, ScheduleSlot.start_time)
        .all()
    )
    return jsonify([_slot_to_event(s) for s in slots])


# ---------------------------------------------------------------------------
# GET /provider/templates  — HTML
# ---------------------------------------------------------------------------


@provider_bp.route("/templates")
@_require_provider
def templates_list():
    templates = (
        ScheduleTemplate.query
        .filter_by(provider_id=current_user.id)
        .order_by(ScheduleTemplate.valid_from.desc())
        .all()
    )
    modalities = Modality.query.filter_by(is_active=True).order_by(Modality.name).all()
    return render_template(
        "provider/templates.html",
        templates=templates,
        modalities=modalities,
    )


# ---------------------------------------------------------------------------
# POST /provider/calendar/slot/create  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/calendar/slot/create", methods=["POST"])
@_require_provider
def slot_create():
    data = request.get_json(force=True) or {}
    try:
        slot_date = _parse_date(data["date"])
        start = _parse_time(data["start_time"])
    except (KeyError, ValueError) as exc:
        return jsonify({"error": f"Parâmetro inválido: {exc}"}), 400

    duration = int(data.get("duration_min", 60))
    capacity = int(data.get("max_capacity", 10))
    modality_id = data.get("modality_id") or None

    end = (datetime.combine(slot_date, start) + timedelta(minutes=duration)).time()

    existing = ScheduleSlot.query.filter_by(
        provider_id=current_user.id,
        date=slot_date,
        start_time=start,
    ).first()
    if existing:
        return jsonify({"error": "Já existe um horário nesta data e hora."}), 409

    slot = ScheduleSlot(
        provider_id=current_user.id,
        modality_id=modality_id,
        date=slot_date,
        start_time=start,
        end_time=end,
        max_capacity=capacity,
        status="active",
    )
    db.session.add(slot)
    db.session.commit()
    return jsonify({"slot": _slot_to_dict(slot), "event": _slot_to_event(slot)}), 201


# ---------------------------------------------------------------------------
# POST /provider/calendar/slot/<id>/delete  — AJAX (duplo clique)
# ---------------------------------------------------------------------------


@provider_bp.route("/calendar/slot/<int:slot_id>/delete", methods=["POST"])
@_require_provider
def slot_delete(slot_id: int):
    slot = ScheduleSlot.query.filter_by(
        id=slot_id, provider_id=current_user.id,
    ).first_or_404()

    confirmed_bookings = Booking.query.filter_by(
        slot_id=slot.id, status=BookingStatus.CONFIRMED,
    ).all()

    if not confirmed_bookings:
        db.session.delete(slot)
        db.session.commit()
        return jsonify({"message": "Horário removido.", "action": "deleted"})

    slot.status = "cancelled"
    now = datetime.utcnow()
    for booking in confirmed_bookings:
        booking.status = BookingStatus.CANCELLED
        booking.cancelled_at = now
        booking.cancel_reason = "Horário cancelado pelo prestador."

    db.session.commit()
    return jsonify({
        "message": f"Horário cancelado. {len(confirmed_bookings)} aluno(s) afetado(s).",
        "action": "cancelled",
        "affected_bookings": len(confirmed_bookings),
    })


# ---------------------------------------------------------------------------
# POST /provider/slot/<id>/update-capacity  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/slot/<int:slot_id>/update-capacity", methods=["POST"])
@_require_provider
def slot_update_capacity(slot_id: int):
    """Altera o número máximo de vagas de um slot."""
    slot = ScheduleSlot.query.filter_by(
        id=slot_id, provider_id=current_user.id,
    ).first_or_404()

    data = request.get_json(force=True) or {}
    try:
        new_capacity = int(data["max_capacity"])
        if new_capacity < 1:
            raise ValueError
    except (KeyError, ValueError):
        return jsonify({"error": "max_capacity deve ser um inteiro ≥ 1."}), 400

    if new_capacity < slot.booked_count:
        return jsonify({
            "error": (
                f"Não é possível reduzir para {new_capacity} vagas: "
                f"já existem {slot.booked_count} inscritos."
            )
        }), 409

    slot.max_capacity = new_capacity
    db.session.commit()
    return jsonify({"slot": _slot_to_dict(slot), "event": _slot_to_event(slot)})


# ---------------------------------------------------------------------------
# POST /provider/day/<date_str>/block  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/day/<date_str>/block", methods=["POST"])
@_require_provider
def day_block(date_str: str):
    """
    Bloqueia um dia inteiro (feriado/viagem):
    cancela todos os slots ativos do prestador nessa data e seus bookings.
    """
    try:
        target_date = _parse_date(date_str)
    except ValueError:
        return jsonify({"error": "Data inválida."}), 400

    data = request.get_json(force=True) or {}
    reason = data.get("reason", "Dia bloqueado pelo prestador.")

    slots = ScheduleSlot.query.filter_by(
        provider_id=current_user.id,
        date=target_date,
        status="active",
    ).all()

    if not slots:
        return jsonify({"message": "Nenhum slot ativo neste dia.", "cancelled": 0})

    now = datetime.utcnow()
    total_bookings = 0
    for slot in slots:
        slot.status = "cancelled"
        slot.cancel_reason = reason
        bookings = Booking.query.filter_by(
            slot_id=slot.id, status=BookingStatus.CONFIRMED,
        ).all()
        for b in bookings:
            b.status = BookingStatus.CANCELLED
            b.cancelled_at = now
            b.cancel_reason = reason
            total_bookings += 1

    db.session.commit()
    return jsonify({
        "message": f"{len(slots)} slot(s) cancelado(s). {total_bookings} aluno(s) afetado(s).",
        "cancelled_slots": len(slots),
        "affected_bookings": total_bookings,
        "date": date_str,
    })


# ---------------------------------------------------------------------------
# POST /provider/templates/create  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/templates/create", methods=["POST"])
@_require_provider
def templates_create():
    data = request.get_json(force=True) or {}
    required = ("weekdays", "start_time", "end_time", "valid_from")
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify({"error": f"Campos obrigatórios ausentes: {missing}"}), 400

    try:
        weekdays = list(data["weekdays"])
        if not weekdays or not all(isinstance(d, int) and 0 <= d <= 6 for d in weekdays):
            raise ValueError("weekdays deve ser lista de inteiros 0–6")
        start = _parse_time(data["start_time"])
        end = _parse_time(data["end_time"])
        if end <= start:
            raise ValueError("end_time deve ser posterior a start_time")
        valid_from = _parse_date(data["valid_from"])
        valid_until = _parse_date(data["valid_until"]) if data.get("valid_until") else None
        if valid_until and valid_until < valid_from:
            raise ValueError("valid_until deve ser posterior a valid_from")
    except (KeyError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400

    template = ScheduleTemplate(
        provider_id=current_user.id,
        modality_id=data.get("modality_id") or None,
        weekdays=weekdays,
        start_time=start,
        end_time=end,
        slot_duration_min=int(data.get("slot_duration_min", 60)),
        max_capacity=int(data.get("max_capacity", 10)),
        valid_from=valid_from,
        valid_until=valid_until,
        is_active=True,
    )
    db.session.add(template)
    db.session.flush()

    created_slots = generate_slots_from_template(template)
    db.session.commit()

    return jsonify({
        "template_id": template.id,
        "slots_created": len(created_slots),
        "message": f"Template criado. {len(created_slots)} horário(s) gerado(s).",
    }), 201


# ---------------------------------------------------------------------------
# POST /provider/templates/<id>/edit  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/templates/<int:tpl_id>/edit", methods=["POST"])
@_require_provider
def templates_edit(tpl_id: int):
    template = ScheduleTemplate.query.filter_by(
        id=tpl_id, provider_id=current_user.id,
    ).first_or_404()

    data = request.get_json(force=True) or {}
    if "max_capacity" in data:
        template.max_capacity = int(data["max_capacity"])
    if "valid_until" in data:
        template.valid_until = _parse_date(data["valid_until"]) if data["valid_until"] else None
    if "is_active" in data:
        template.is_active = bool(data["is_active"])
    if "modality_id" in data:
        template.modality_id = data["modality_id"] or None

    db.session.commit()
    return jsonify({"message": "Template atualizado.", "template_id": template.id})


# ---------------------------------------------------------------------------
# POST /provider/templates/<id>/delete  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/templates/<int:tpl_id>/delete", methods=["POST"])
@_require_provider
def templates_delete(tpl_id: int):
    template = ScheduleTemplate.query.filter_by(
        id=tpl_id, provider_id=current_user.id,
    ).first_or_404()

    template.is_active = False
    today = date.today()
    future_empty = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.template_id == template.id,
            ScheduleSlot.date >= today,
            ScheduleSlot.status == "active",
        )
        .all()
    )
    cancelled = sum(
        1 for s in future_empty
        if s.available_spots == s.max_capacity
        and not setattr(s, "status", "cancelled")  # trick: setattr always returns None → falsy → counted
    )
    # Simpler:
    cancelled = 0
    for s in future_empty:
        if s.available_spots == s.max_capacity:
            s.status = "cancelled"
            cancelled += 1

    db.session.commit()
    return jsonify({"message": "Template desativado.", "empty_slots_cancelled": cancelled})


# ---------------------------------------------------------------------------
# GET /provider/slot/<id>/attendees  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/slot/<int:slot_id>/attendees")
@_require_provider
def slot_attendees(slot_id: int):
    slot = ScheduleSlot.query.filter_by(
        id=slot_id, provider_id=current_user.id,
    ).first_or_404()

    bookings = Booking.query.filter_by(slot_id=slot.id).all()
    attendees = []
    for b in bookings:
        attendees.append({
            "booking_id": b.id,
            "client_id": b.client_id,
            "client_name": b.client.name if b.client else "—",
            "status": b.status.value,
            "booked_at": b.booked_at.isoformat(),
            "checked_in_at": b.checked_in_at.isoformat() if b.checked_in_at else None,
            "cancelled_at": b.cancelled_at.isoformat() if b.cancelled_at else None,
        })

    return jsonify({
        "slot": _slot_to_dict(slot),
        "attendees": attendees,
        "confirmed_count": sum(1 for b in bookings if b.status == BookingStatus.CONFIRMED),
    })


# ---------------------------------------------------------------------------
# POST /provider/slot/<id>/cancel  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/slot/<int:slot_id>/cancel", methods=["POST"])
@_require_provider
def slot_cancel(slot_id: int):
    slot = ScheduleSlot.query.filter_by(
        id=slot_id, provider_id=current_user.id,
    ).first_or_404()

    if slot.status == "cancelled":
        return jsonify({"error": "Este horário já está cancelado."}), 409

    data = request.get_json(force=True) or {}
    reason = data.get("reason", "Cancelado pelo prestador.")
    slot.status = "cancelled"
    slot.cancel_reason = reason

    now = datetime.utcnow()
    affected = Booking.query.filter_by(
        slot_id=slot.id, status=BookingStatus.CONFIRMED,
    ).all()
    for b in affected:
        b.status = BookingStatus.CANCELLED
        b.cancelled_at = now
        b.cancel_reason = reason

    db.session.commit()
    return jsonify({
        "message": "Slot cancelado.",
        "affected_bookings": len(affected),
        "reason": reason,
    })


# ---------------------------------------------------------------------------
# POST /provider/checkin/<booking_id>  — AJAX
# ---------------------------------------------------------------------------


@provider_bp.route("/checkin/<int:booking_id>", methods=["POST"])
@_require_provider
def checkin(booking_id: int):
    booking = (
        Booking.query
        .join(ScheduleSlot)
        .filter(
            Booking.id == booking_id,
            ScheduleSlot.provider_id == current_user.id,
        )
        .first_or_404()
    )

    if booking.status != BookingStatus.CONFIRMED:
        return jsonify({
            "error": f"Status atual é '{booking.status.value}', não é possível fazer check-in."
        }), 409

    booking.checked_in_at = datetime.utcnow()
    booking.status = BookingStatus.COMPLETED
    db.session.commit()

    return jsonify({
        "message": "Presença registrada.",
        "booking_id": booking.id,
        "client_name": booking.client.name if booking.client else "—",
        "checked_in_at": booking.checked_in_at.isoformat(),
    })
