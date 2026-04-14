# app/routes/auth.py
"""
Autenticação básica — /auth

GET  /auth/login   → Formulário de login
POST /auth/login   → Processa login
GET  /auth/logout  → Encerra sessão
GET  /             → Redireciona para login ou dashboard
"""

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app import db
from app.models.user import User

auth_bp = Blueprint("auth", __name__, url_prefix="/auth", template_folder="../templates")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_by_role(current_user)

    if request.method == "POST":
        email    = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password) and user.is_active:
            login_user(user, remember=True)
            next_url = request.args.get("next")
            if next_url and next_url.startswith("/"):
                return redirect(next_url)
            return _redirect_by_role(user)

        flash("E-mail ou senha incorretos.", "error")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))


def _redirect_by_role(user: User):
    if user.is_instructor:
        return redirect(url_for("provider.dashboard"))
    if user.role == "admin":
        return redirect(url_for("provider.dashboard"))
    return redirect(url_for("student.schedule"))
