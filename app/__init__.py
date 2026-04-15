# app/__init__.py
"""
Application factory for academia2.
"""

import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_override: dict | None = None) -> Flask:
    app = Flask(__name__)

    # --- Defaults --------------------------------------------------------
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key-mude-em-producao")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///academia.db")
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    if config_override:
        app.config.update(config_override)

    # --- Extensions ------------------------------------------------------
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # --- Context processors ----------------------------------------------
    from datetime import datetime

    @app.context_processor
    def inject_globals():
        return {"now": datetime.now}

    @login_manager.user_loader
    def load_user(user_id: str):
        from app.models.user import User
        return db.session.get(User, int(user_id))

    # --- Root redirect ---------------------------------------------------
    from flask import redirect, url_for

    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.role == "admin":
                return redirect(url_for("admin.leads"))
            if current_user.is_instructor:
                return redirect(url_for("provider.dashboard"))
            return redirect(url_for("student.schedule"))
        return redirect(url_for("auth.login"))

    # --- Blueprints ------------------------------------------------------
    from app.routes.auth import auth_bp
    from app.routes.provider import provider_bp
    from app.routes.student import student_bp
    from app.routes.onboarding import onboarding_bp
    from app.routes.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(provider_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(onboarding_bp)
    app.register_blueprint(admin_bp)

    return app
