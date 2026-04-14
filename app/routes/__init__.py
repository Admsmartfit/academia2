# app/routes/__init__.py
from app.routes.auth import auth_bp
from app.routes.provider import provider_bp
from app.routes.student import student_bp

__all__ = ["auth_bp", "provider_bp", "student_bp"]
