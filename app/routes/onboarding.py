# app/routes/onboarding.py
"""
Blueprint de Onboarding — /onboarding

Rotas HTML:
    GET  /onboarding/quiz                          → Quiz de perfil (5 perguntas)
    POST /onboarding/quiz/submit                   → Processa respostas
    GET  /onboarding/suggestion                    → Resultado: modalidades sugeridas
    GET  /onboarding/parq                          → Triagem de saúde EZBody
    POST /onboarding/parq/submit                   → Valida PAR-Q
    GET  /onboarding/book-demo/<int:modality_id>   → Grade de horários demo
    GET  /onboarding/confirmed                     → Confirmação pós-agendamento
    GET  /onboarding/convert                       → Conversão pós-demo
    GET  /onboarding/set-password                  → Define senha após checkout
    POST /onboarding/set-password                  → Salva senha e faz login

Rotas AJAX:
    POST /onboarding/book-demo/<int:modality_id>/confirm   → Confirma reserva demo
    GET  /onboarding/book-demo/<int:modality_id>/slots     → Slots disponíveis (AJAX)
    GET  /onboarding/book-demo/<int:modality_id>/alts      → Alternativas por turno
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from functools import wraps

from flask import (Blueprint, flash, jsonify, redirect, render_template,
                   request, url_for)
from flask_login import current_user, login_user

from app import db
from app.models.booking import Booking, BookingStatus
from app.models.lead_profile import LeadProfile
from app.models.modality import Modality
from app.models.schedule_slot import ScheduleSlot
from app.models.user import User
from app.services.onboarding import (
    filter_slots_by_turno,
    suggest_demo_slots,
    suggest_modalities,
    validate_demo_booking,
)

onboarding_bp = Blueprint(
    "onboarding", __name__,
    url_prefix="/onboarding",
    template_folder="../templates",
)

_DEMO_WINDOW_DAYS = 20
_WEEKDAY_BR_SHORT = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
_WEEKDAY_BR_LONG  = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_login(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated


def _get_or_create_lead() -> LeadProfile:
    """Retorna o LeadProfile do usuário atual, criando se não existir."""
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()
    if not lead:
        lead = LeadProfile(user_id=current_user.id, onboarding_step="quiz")
        db.session.add(lead)
        db.session.flush()
    return lead


def _modality_by_id(modality_id: int) -> Modality:
    return Modality.query.get_or_404(modality_id)


def _slot_serialise(s: ScheduleSlot, today: date) -> dict:
    days_away = (s.date - today).days
    return {
        "id":            s.id,
        "date":          s.date.isoformat(),
        "weekday":       _WEEKDAY_BR_SHORT[s.date.weekday()],
        "start_time":    s.start_time.strftime("%H:%M"),
        "end_time":      s.end_time.strftime("%H:%M"),
        "available":     s.available_spots,
        "max":           s.max_capacity,
        "pct":           s.occupancy_pct,
        "provider_name": s.provider.name if s.provider else "—",
        "days_away":     days_away,
        "is_today":      days_away == 0,
        "is_tomorrow":   days_away == 1,
    }


# ---------------------------------------------------------------------------
# GET /onboarding/quiz
# ---------------------------------------------------------------------------

@onboarding_bp.route("/quiz")
@_require_login
def quiz():
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()
    if lead and lead.quiz_completed_at:
        return redirect(url_for("onboarding.suggestion"))
    return render_template("onboarding/quiz.html")


# ---------------------------------------------------------------------------
# POST /onboarding/quiz/submit
# ---------------------------------------------------------------------------

@onboarding_bp.route("/quiz/submit", methods=["POST"])
@_require_login
def quiz_submit():
    answers = {
        "objetivo":   request.form.get("objetivo", ""),
        "tempo":      request.form.get("tempo", ""),
        "frequencia": request.form.get("frequencia", ""),
        "experiencia":request.form.get("experiencia", ""),
        "turno":      request.form.get("turno", ""),
    }

    lead = _get_or_create_lead()
    lead.objetivo         = answers["objetivo"]
    lead.tempo_disponivel = answers["tempo"]
    lead.frequencia       = answers["frequencia"]
    lead.experiencia      = answers["experiencia"]
    lead.turno            = answers["turno"]
    lead.modalities_suggested = suggest_modalities(answers)
    lead.quiz_completed_at    = datetime.utcnow()
    lead.onboarding_step      = "suggestion"

    # Atualiza lead_source se ainda não definido
    if not current_user.lead_source:
        current_user.lead_source = "quiz_organic"

    db.session.commit()
    return redirect(url_for("onboarding.suggestion"))


# ---------------------------------------------------------------------------
# GET /onboarding/suggestion
# ---------------------------------------------------------------------------

@onboarding_bp.route("/suggestion")
@_require_login
def suggestion():
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()
    if not lead or not lead.quiz_completed_at:
        return redirect(url_for("onboarding.quiz"))

    suggestions = lead.modalities_suggested or []

    # Busca objetos Modality correspondentes
    modalities = []
    for slug in suggestions:
        m = Modality.query.filter(Modality.name.ilike(f"%{slug.replace('_', ' ')}%")).first()
        if not slug == "ezbody":
            m = Modality.query.filter(Modality.name.ilike(f"%muscula%")).first() if slug == "musculacao" else m
        else:
            m = Modality.query.filter(Modality.name.ilike("%EZBody%")).first() \
                or Modality.query.filter(Modality.name.ilike("%EMS%")).first() \
                or Modality.query.filter(Modality.name.ilike("%ems%")).first()
        modalities.append({"slug": slug, "modality": m})

    # Verifica se PAR-Q é necessário (EZBody sugerido e ainda não feito)
    needs_parq = "ezbody" in suggestions and lead.parq_passed is None

    return render_template(
        "onboarding/suggestion.html",
        lead=lead,
        suggestions=suggestions,
        modalities=modalities,
        needs_parq=needs_parq,
        weekday_long=_WEEKDAY_BR_LONG,
    )


# ---------------------------------------------------------------------------
# GET /onboarding/parq
# ---------------------------------------------------------------------------

@onboarding_bp.route("/parq")
@_require_login
def parq():
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()
    if not lead or not lead.quiz_completed_at:
        return redirect(url_for("onboarding.quiz"))
    if "ezbody" not in (lead.modalities_suggested or []):
        return redirect(url_for("onboarding.suggestion"))
    return render_template("onboarding/parq.html", lead=lead)


# ---------------------------------------------------------------------------
# POST /onboarding/parq/submit
# ---------------------------------------------------------------------------

@onboarding_bp.route("/parq/submit", methods=["POST"])
@_require_login
def parq_submit():
    lead = _get_or_create_lead()

    answers = {
        "marcapasso":   request.form.get("q1") == "yes",
        "gravida":      request.form.get("q2") == "yes",
        "epilepsia":    request.form.get("q3") == "yes",
        "feridas":      request.form.get("q4") == "yes",
        "linfedema":    request.form.get("q5") == "yes",
        "emagrecedor":  request.form.get("q6") == "yes",
    }
    lead.parq_answers = answers

    blockers = ["marcapasso", "gravida", "epilepsia", "feridas"]
    blocked  = any(answers[k] for k in blockers)

    if blocked:
        lead.parq_passed = False
        # Remove ezbody das sugestões
        sugs = lead.modalities_suggested or []
        lead.modalities_suggested = [s for s in sugs if s != "ezbody"]
        lead.onboarding_step = "suggestion"
        db.session.commit()
        flash(
            "Com base na triagem, a aula de EZBody não está disponível para você neste momento. "
            "Mas a Musculação é uma ótima opção!",
            "warning",
        )
        return redirect(url_for("onboarding.suggestion"))

    lead.parq_passed     = True
    lead.onboarding_step = "booking"
    db.session.commit()

    # Busca a modalidade EZBody para redirecionar ao agendamento
    ezb = (Modality.query.filter(Modality.name.ilike("%EZBody%")).first()
           or Modality.query.filter(Modality.name.ilike("%EMS%")).first())
    if ezb:
        return redirect(url_for("onboarding.book_demo", modality_id=ezb.id))
    return redirect(url_for("onboarding.suggestion"))


# ---------------------------------------------------------------------------
# GET /onboarding/book-demo/<modality_id>
# ---------------------------------------------------------------------------

@onboarding_bp.route("/book-demo/<int:modality_id>")
@_require_login
def book_demo(modality_id: int):
    lead     = LeadProfile.query.filter_by(user_id=current_user.id).first()
    modality = _modality_by_id(modality_id)
    today    = date.today()
    turno    = request.args.get("turno", lead.turno if lead else "") or ""

    # Verifica se EZBody requer PAR-Q ainda não feito
    is_ezbody = "ezb" in modality.name.lower() or "ems" in modality.name.lower()
    if is_ezbody and lead and lead.parq_passed is None and "ezbody" in (lead.modalities_suggested or []):
        return redirect(url_for("onboarding.parq"))

    # Busca slots dos próximos 20 dias para esta modalidade
    until = today + timedelta(days=_DEMO_WINDOW_DAYS)
    slots_raw = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.modality_id == modality_id,
            ScheduleSlot.date >= today,
            ScheduleSlot.date <= until,
            ScheduleSlot.status == "active",
        )
        .order_by(ScheduleSlot.date, ScheduleSlot.start_time)
        .all()
    )
    slots_raw = [s for s in slots_raw if s.available_spots > 0]

    # Agrupa por data
    from collections import defaultdict
    slots_by_date: dict = defaultdict(list)
    for s in filter_slots_by_turno(slots_raw, turno) if turno else slots_raw:
        slots_by_date[s.date.isoformat()].append(_slot_serialise(s, today))

    # Datas disponíveis (strip de 20 dias)
    date_strip = []
    for i in range(_DEMO_WINDOW_DAYS + 1):
        d = today + timedelta(days=i)
        ds = d.isoformat()
        date_strip.append({
            "date":    ds,
            "day":     d.day,
            "weekday": _WEEKDAY_BR_SHORT[d.weekday()],
            "has_slots": bool(slots_by_date.get(ds)),
        })

    # Alertas nutricionais EZBody
    show_nutrition_alert = is_ezbody and lead and lead.parq_answers and lead.parq_answers.get("emagrecedor")
    show_linfedema_alert = is_ezbody and lead and lead.parq_answers and lead.parq_answers.get("linfedema")

    import json
    return render_template(
        "onboarding/book_demo.html",
        modality=modality,
        lead=lead,
        today=today,
        turno=turno,
        date_strip=date_strip,
        slots_by_date_json=json.dumps(dict(slots_by_date)),
        is_ezbody=is_ezbody,
        show_nutrition_alert=show_nutrition_alert,
        show_linfedema_alert=show_linfedema_alert,
        weekday_long=_WEEKDAY_BR_LONG,
    )


# ---------------------------------------------------------------------------
# POST /onboarding/book-demo/<modality_id>/confirm  — AJAX
# ---------------------------------------------------------------------------

@onboarding_bp.route("/book-demo/<int:modality_id>/confirm", methods=["POST"])
@_require_login
def book_demo_confirm(modality_id: int):
    data    = request.get_json(silent=True) or {}
    slot_id = data.get("slot_id")
    if not slot_id:
        return jsonify({"error": "slot_id obrigatório."}), 400

    slot = ScheduleSlot.query.get_or_404(slot_id)
    if slot.modality_id != modality_id:
        return jsonify({"error": "Slot não pertence a esta modalidade."}), 400

    ok, err = validate_demo_booking(current_user, slot)
    if not ok:
        return jsonify({"error": err}), 409

    booking = Booking(
        client_id       = current_user.id,
        slot_id         = slot.id,
        subscription_id = None,
        status          = BookingStatus.CONFIRMED,
        cost_at_booking = 0,
        booking_type    = "demo",
    )
    db.session.add(booking)

    # Atualiza LeadProfile
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()
    if lead:
        lead.onboarding_step = "confirmed"
        lead.demo_booked_at  = datetime.utcnow()

    db.session.commit()

    return jsonify({
        "message":    "Aula demonstrativa agendada com sucesso!",
        "booking_id": booking.id,
        "redirect":   url_for("onboarding.confirmed"),
    })


# ---------------------------------------------------------------------------
# GET /onboarding/book-demo/<modality_id>/slots  — AJAX
# ---------------------------------------------------------------------------

@onboarding_bp.route("/book-demo/<int:modality_id>/slots")
@_require_login
def book_demo_slots(modality_id: int):
    today  = date.today()
    turno  = request.args.get("turno", "")
    raw_date = request.args.get("date", today.isoformat())
    try:
        sel_date = date.fromisoformat(raw_date)
    except ValueError:
        sel_date = today

    until  = today + timedelta(days=_DEMO_WINDOW_DAYS)
    if sel_date > until or sel_date < today:
        return jsonify({"slots": [], "date": raw_date})

    slots_raw = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.modality_id == modality_id,
            ScheduleSlot.date == sel_date,
            ScheduleSlot.status == "active",
        )
        .order_by(ScheduleSlot.start_time)
        .all()
    )
    slots_raw = [s for s in slots_raw if s.available_spots > 0]
    if turno:
        slots_raw = filter_slots_by_turno(slots_raw, turno)

    return jsonify({
        "date":    raw_date,
        "weekday": _WEEKDAY_BR_LONG[sel_date.weekday()],
        "slots":   [_slot_serialise(s, today) for s in slots_raw],
    })


# ---------------------------------------------------------------------------
# GET /onboarding/book-demo/<modality_id>/alts  — AJAX
# ---------------------------------------------------------------------------

@onboarding_bp.route("/book-demo/<int:modality_id>/alts")
@_require_login
def book_demo_alts(modality_id: int):
    today = date.today()
    turno = request.args.get("turno", "")
    alts  = suggest_demo_slots(modality_id, turno, today, limit=8)
    return jsonify({
        "alternatives": [_slot_serialise(s, today) for s in alts],
    })


# ---------------------------------------------------------------------------
# GET /onboarding/confirmed
# ---------------------------------------------------------------------------

@onboarding_bp.route("/confirmed")
@_require_login
def confirmed():
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()

    # Busca a reserva demo mais recente
    demo_booking = (
        Booking.query
        .filter_by(client_id=current_user.id, booking_type="demo",
                   status=BookingStatus.CONFIRMED)
        .order_by(Booking.booked_at.desc())
        .first()
    )

    slot = demo_booking.slot if demo_booking else None
    modality = slot.modality if slot else None

    return render_template(
        "onboarding/confirmed.html",
        lead=lead,
        booking=demo_booking,
        slot=slot,
        modality=modality,
        weekday_long=_WEEKDAY_BR_LONG,
    )


# ---------------------------------------------------------------------------
# GET /onboarding/convert
# ---------------------------------------------------------------------------

@onboarding_bp.route("/convert")
@_require_login
def convert():
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()

    # Busca a demo realizada mais recente
    demo_booking = (
        Booking.query
        .filter_by(client_id=current_user.id, booking_type="demo",
                   status=BookingStatus.COMPLETED)
        .order_by(Booking.checked_in_at.desc())
        .first()
    )

    slot     = demo_booking.slot if demo_booking else None
    modality = slot.modality if slot else None

    # Planos recomendados com base no perfil
    plans = _build_plan_suggestions(lead)

    return render_template(
        "onboarding/convert.html",
        lead=lead,
        booking=demo_booking,
        slot=slot,
        modality=modality,
        plans=plans,
    )


# ---------------------------------------------------------------------------
# POST /onboarding/convert/select
# ---------------------------------------------------------------------------

@onboarding_bp.route("/convert/select", methods=["POST"])
@_require_login
def convert_select():
    lead = LeadProfile.query.filter_by(user_id=current_user.id).first()
    if lead:
        lead.onboarding_step = "converted"
        lead.converted_at    = datetime.utcnow()
        db.session.commit()
    # Redireciona para a grade de agendamento (onde o aluno comprará créditos futuramente)
    flash("Ótima escolha! Entre em contato com a recepção para finalizar sua matrícula.", "success")
    return redirect(url_for("student.schedule"))


# ---------------------------------------------------------------------------
# Helper privado — Sugestão de Planos
# ---------------------------------------------------------------------------

def _build_plan_suggestions(lead: LeadProfile | None) -> list[dict]:
    """Monta lista de planos sugeridos com base no perfil do lead."""
    plans = []

    freq = lead.frequencia if lead else ""
    sugs = lead.modalities_suggested if lead else []

    if "ezbody" in (sugs or []):
        credits_ezb = 4 if freq in ["1_2x"] else 8
        plans.append({
            "key":         "ezbody_semanal",
            "title":       "Plano EZBody Semanal",
            "description": "1x EZBody por semana — 20 min de alta intensidade",
            "credits":     credits_ezb,
            "icon":        "fas fa-bolt",
            "color":       "#6f42c1",
            "highlight":   True,
        })

    if "musculacao" in (sugs or []):
        credits_musc = 8 if freq in ["1_2x"] else 12
        plans.append({
            "key":         "musculacao_semanal",
            "title":       "Plano Musculação",
            "description": "2–3x Musculação por semana — hipertrofia e definição",
            "credits":     credits_musc,
            "icon":        "fas fa-dumbbell",
            "color":       "#FF6B35",
            "highlight":   False,
        })

    if "ezbody" in (sugs or []) and "musculacao" in (sugs or []):
        credits_hybrid = 16 if freq in ["3_4x", "todos_dias"] else 12
        plans.append({
            "key":         "hibrido",
            "title":       "Plano Híbrido Completo",
            "description": "2x EZBody + 3x Musculação/semana — o melhor dos dois mundos",
            "credits":     credits_hybrid,
            "icon":        "fas fa-fire",
            "color":       "#198754",
            "highlight":   len(plans) == 2,
        })

    if not plans:
        plans.append({
            "key":         "starter",
            "title":       "Plano Iniciante",
            "description": "Comece com 4 aulas e descubra o seu ritmo",
            "credits":     4,
            "icon":        "fas fa-star",
            "color":       "#FF6B35",
            "highlight":   True,
        })

    return plans


# ---------------------------------------------------------------------------
# GET/POST /onboarding/set-password
# ---------------------------------------------------------------------------

@onboarding_bp.route("/set-password", methods=["GET", "POST"])
def set_password():
    """
    Frictionless onboarding: the user was created with a random password
    during checkout (or by the admin). This page lets them choose their
    own password and get auto-logged in.

    Expects ?token=<email_b64> in the query string (GET) or a hidden field
    on POST.  Falls back to current_user if already authenticated.
    """
    import base64

    # Resolve the user either from token or current session
    token = request.args.get("token") or request.form.get("token", "")
    user = None

    if token:
        try:
            email = base64.urlsafe_b64decode(token.encode()).decode()
            user  = User.query.filter_by(email=email).first()
        except Exception:
            pass

    if user is None and current_user.is_authenticated:
        user = current_user

    if user is None:
        flash("Link inválido ou expirado. Faça login para continuar.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        password = request.form.get("password", "").strip()
        confirm  = request.form.get("confirm", "").strip()

        if len(password) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "danger")
            return render_template("onboarding/set_password.html", token=token, user=user)

        if password != confirm:
            flash("As senhas não coincidem.", "danger")
            return render_template("onboarding/set_password.html", token=token, user=user)

        user.set_password(password)
        db.session.commit()

        login_user(user)
        flash("Senha definida com sucesso! Bem-vindo(a).", "success")

        # Redirect based on role
        if user.role == "admin":
            return redirect(url_for("admin.leads"))
        if user.is_instructor:
            return redirect(url_for("provider.dashboard"))

        # Check if onboarding is pending
        lead = LeadProfile.query.filter_by(user_id=user.id).first()
        if lead and lead.onboarding_step not in ("converted",):
            return redirect(url_for("onboarding.quiz"))
        return redirect(url_for("student.schedule"))

    return render_template("onboarding/set_password.html", token=token, user=user)
