# app/routes/admin.py
"""
Blueprint Admin — /admin

Rotas HTML:
    GET  /admin/leads                   → Lista de leads com filtro por etapa
    GET  /admin/leads/funnel            → Dashboard de métricas do funil
    GET  /admin/leads/<id>              → Perfil completo do lead
    POST /admin/leads/create            → Criar lead manual
    POST /admin/leads/<id>/convert      → Marcar como convertido

    GET  /admin/users                   → Lista de usuários com filtros
    POST /admin/users/create            → Criar usuário (instrutor/admin)
    POST /admin/users/<id>/reset        → Redefinir senha
    POST /admin/users/<id>/toggle       → Ativar/desativar usuário
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from flask import (Blueprint, flash, redirect, render_template,
                   request, url_for)
from flask_login import current_user
from functools import wraps

from app import db
from app.models.booking import Booking
from app.models.lead_profile import LeadProfile
from app.models.schedule_slot import ScheduleSlot
from app.models.user import User

admin_bp = Blueprint(
    "admin", __name__,
    url_prefix="/admin",
    template_folder="../templates",
)

_FUNNEL_STEPS = [
    ("quiz",          "Quiz"),
    ("suggestion",    "Sugestão"),
    ("parq",          "PAR-Q"),
    ("booking",       "Agendando"),
    ("confirmed",     "Demo Agendada"),
    ("demo_realizada","Demo Realizada"),
    ("converted",     "Matriculado"),
]


# ---------------------------------------------------------------------------
# Decorator
# ---------------------------------------------------------------------------

def _require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Acesso restrito a administradores.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# GET /admin/leads
# ---------------------------------------------------------------------------

@admin_bp.route("/leads")
@_require_admin
def leads():
    step_filter = request.args.get("step", "")

    q = LeadProfile.query.join(User).order_by(LeadProfile.created_at.desc())
    if step_filter:
        q = q.filter(LeadProfile.onboarding_step == step_filter)

    all_leads  = q.all()
    step_counts = Counter(
        lp.onboarding_step for lp in LeadProfile.query.all()
    )

    return render_template(
        "admin/leads/index.html",
        leads=all_leads,
        funnel_steps=_FUNNEL_STEPS,
        step_filter=step_filter,
        step_counts=step_counts,
    )


# ---------------------------------------------------------------------------
# GET /admin/leads/funnel
# ---------------------------------------------------------------------------

@admin_bp.route("/leads/funnel")
@_require_admin
def leads_funnel():
    all_leads = LeadProfile.query.all()
    step_counts = Counter(lp.onboarding_step for lp in all_leads)

    total_quiz      = len(all_leads)
    total_confirmed = sum(1 for lp in all_leads if lp.onboarding_step in
                          ("confirmed", "demo_realizada", "converted"))
    total_demo_done = sum(1 for lp in all_leads if lp.onboarding_step in
                          ("demo_realizada", "converted"))
    total_converted = step_counts.get("converted", 0)

    # Taxa de conversão
    rate_quiz_demo = (
        round(total_confirmed / total_quiz * 100) if total_quiz else 0
    )
    rate_demo_mat  = (
        round(total_converted / total_demo_done * 100) if total_demo_done else 0
    )

    # Modalidade mais demandada nas demos
    demo_bookings = (
        Booking.query
        .join(ScheduleSlot)
        .filter(Booking.booking_type == "demo")
        .all()
    )
    modality_counter: Counter = Counter()
    turno_counter: Counter    = Counter()
    for b in demo_bookings:
        if b.slot and b.slot.modality:
            modality_counter[b.slot.modality.name] += 1
        if b.slot:
            h = b.slot.start_time.hour
            if 6 <= h < 12:
                turno_counter["Manhã"] += 1
            elif 12 <= h < 18:
                turno_counter["Tarde"] += 1
            elif 18 <= h < 22:
                turno_counter["Noite"] += 1
            else:
                turno_counter["Outros"] += 1

    # Leads travados em cada etapa (há mais de 3 dias sem avançar)
    from datetime import date, timedelta
    three_days_ago = datetime.utcnow() - timedelta(days=3)
    stuck_leads = [
        lp for lp in all_leads
        if lp.onboarding_step not in ("converted",)
        and lp.updated_at < three_days_ago
    ]

    return render_template(
        "admin/leads/funnel.html",
        funnel_steps=_FUNNEL_STEPS,
        step_counts=step_counts,
        total_quiz=total_quiz,
        total_confirmed=total_confirmed,
        total_demo_done=total_demo_done,
        total_converted=total_converted,
        rate_quiz_demo=rate_quiz_demo,
        rate_demo_mat=rate_demo_mat,
        modality_counter=modality_counter.most_common(5),
        turno_counter=turno_counter.most_common(4),
        stuck_leads=stuck_leads,
    )


# ---------------------------------------------------------------------------
# GET /admin/leads/<id>
# ---------------------------------------------------------------------------

@admin_bp.route("/leads/<int:lead_id>")
@_require_admin
def lead_detail(lead_id: int):
    lead = LeadProfile.query.get_or_404(lead_id)

    demo_bookings = (
        Booking.query
        .filter_by(client_id=lead.user_id, booking_type="demo")
        .order_by(Booking.booked_at.desc())
        .all()
    )

    objetivo_labels = {
        "emagrecer":    "Emagrecer e definir",
        "ganhar_massa": "Ganhar massa muscular",
        "saude":        "Melhorar saúde e disposição",
        "reabilitacao": "Reabilitação / aliviar dores",
        "manutencao":   "Manutenção e qualidade de vida",
    }
    turno_labels = {
        "manha": "Manhã (06–12h)",
        "tarde": "Tarde (12–18h)",
        "noite": "Noite (18–22h)",
        "fds":   "Final de semana",
    }
    freq_labels = {
        "1_2x":      "1–2x por semana",
        "3_4x":      "3–4x por semana",
        "todos_dias":"Todos os dias",
    }

    return render_template(
        "admin/leads/detail.html",
        lead=lead,
        demo_bookings=demo_bookings,
        funnel_steps=_FUNNEL_STEPS,
        objetivo_labels=objetivo_labels,
        turno_labels=turno_labels,
        freq_labels=freq_labels,
    )


# ---------------------------------------------------------------------------
# POST /admin/leads/create
# ---------------------------------------------------------------------------

@admin_bp.route("/leads/create", methods=["POST"])
@_require_admin
def lead_create():
    name  = request.form.get("name", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip().lower()

    if not name or not phone or not email:
        flash("Nome, telefone e e-mail são obrigatórios.", "danger")
        return redirect(url_for("admin.leads"))

    if User.query.filter_by(email=email).first():
        flash("Já existe um usuário com este e-mail.", "warning")
        return redirect(url_for("admin.leads"))

    import secrets
    temp_password = secrets.token_urlsafe(10)

    user = User(
        name=name,
        phone=phone,
        email=email,
        role="student",
        lead_source="admin_manual",
        is_active=True,
    )
    user.set_password(temp_password)
    db.session.add(user)
    db.session.flush()

    lead = LeadProfile(user_id=user.id, onboarding_step="quiz")
    db.session.add(lead)
    db.session.commit()

    flash(
        f"Lead criado! E-mail: {email} | Senha temporária: {temp_password}",
        "success",
    )
    return redirect(url_for("admin.lead_detail", lead_id=lead.id))


# ---------------------------------------------------------------------------
# POST /admin/leads/<id>/convert
# ---------------------------------------------------------------------------

@admin_bp.route("/leads/<int:lead_id>/convert", methods=["POST"])
@_require_admin
def lead_convert(lead_id: int):
    lead = LeadProfile.query.get_or_404(lead_id)
    lead.onboarding_step = "converted"
    lead.converted_at    = datetime.utcnow()
    db.session.commit()
    flash("Lead marcado como convertido.", "success")
    return redirect(url_for("admin.lead_detail", lead_id=lead_id))


# ---------------------------------------------------------------------------
# GET /admin/users
# ---------------------------------------------------------------------------

@admin_bp.route("/users")
@_require_admin
def users():
    role_filter   = request.args.get("role", "")
    status_filter = request.args.get("status", "")
    q_search      = request.args.get("q", "").strip()

    query = User.query.order_by(User.created_at.desc())
    if role_filter:
        query = query.filter(User.role == role_filter)
    if status_filter == "active":
        query = query.filter(User.is_active == True)
    elif status_filter == "inactive":
        query = query.filter(User.is_active == False)
    if q_search:
        like = f"%{q_search}%"
        query = query.filter(
            db.or_(User.name.ilike(like), User.email.ilike(like), User.phone.ilike(like))
        )

    all_users = query.all()

    role_counts = Counter(u.role for u in User.query.all())

    return render_template(
        "admin/users.html",
        users=all_users,
        role_filter=role_filter,
        status_filter=status_filter,
        q_search=q_search,
        role_counts=role_counts,
    )


# ---------------------------------------------------------------------------
# POST /admin/users/create
# ---------------------------------------------------------------------------

@admin_bp.route("/users/create", methods=["POST"])
@_require_admin
def user_create():
    name     = request.form.get("name", "").strip()
    email    = request.form.get("email", "").strip().lower()
    phone    = request.form.get("phone", "").strip()
    role     = request.form.get("role", "student")
    password = request.form.get("password", "").strip()

    if not name or not email or not phone or not password:
        flash("Todos os campos são obrigatórios.", "danger")
        return redirect(url_for("admin.users"))

    if role not in ("student", "instructor", "admin"):
        flash("Papel inválido.", "danger")
        return redirect(url_for("admin.users"))

    if User.query.filter_by(email=email).first():
        flash("Já existe um usuário com este e-mail.", "warning")
        return redirect(url_for("admin.users"))

    user = User(
        name=name,
        email=email,
        phone=phone,
        role=role,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()

    flash(f"Usuário {name} criado com sucesso.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# POST /admin/users/<id>/reset
# ---------------------------------------------------------------------------

@admin_bp.route("/users/<int:user_id>/reset", methods=["POST"])
@_require_admin
def user_reset_password(user_id: int):
    user     = User.query.get_or_404(user_id)
    password = request.form.get("password", "").strip()

    if not password or len(password) < 6:
        flash("A senha deve ter pelo menos 6 caracteres.", "danger")
        return redirect(url_for("admin.users"))

    user.set_password(password)
    db.session.commit()
    flash(f"Senha de {user.name} redefinida com sucesso.", "success")
    return redirect(url_for("admin.users"))


# ---------------------------------------------------------------------------
# POST /admin/users/<id>/toggle
# ---------------------------------------------------------------------------

@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@_require_admin
def user_toggle(user_id: int):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Você não pode desativar sua própria conta.", "warning")
        return redirect(url_for("admin.users"))
    user.is_active = not user.is_active
    db.session.commit()
    status = "ativado" if user.is_active else "desativado"
    flash(f"Usuário {user.name} {status}.", "success")
    return redirect(url_for("admin.users"))
