# app/routes/__init__.py
from app.routes.auth import auth_bp
from app.routes.provider import provider_bp
from app.routes.student import student_bp
from app.routes.onboarding import onboarding_bp
from app.routes.admin import admin_bp

__all__ = ["auth_bp", "provider_bp", "student_bp", "onboarding_bp", "admin_bp"]
