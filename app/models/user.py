# app/models/user.py

from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import enum


class UserRole(enum.Enum):
    ADMIN = "admin"
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    PROVIDER = "provider"  # Alias for instructor as per PRD


class Gender(enum.Enum):
    MALE = "male"
    FEMALE = "female"


class ProfessionalType(enum.Enum):
    """Tipo de profissional para regras de comissao no split."""
    INSTRUCTOR = "instructor"
    TECHNICIAN = "technician"
    NUTRITIONIST = "nutritionist"


class User(UserMixin, db.Model):
    """
    Modelo de usuario do sistema
    """
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    cpf = db.Column(db.String(14), nullable=True)
    gender = db.Column(db.Enum(Gender), nullable=True)
    role = db.Column(db.String(20), default='student')
    
    # Novos campos conforme PRD
    bio = db.Column(db.Text, nullable=True)
    specialties = db.Column(db.JSON, nullable=True)
    schedule_policy_json = db.Column(db.JSON, nullable=True) 
    # Exemplo: {"min_notice_hours": 2, "cancel_deadline_hours": 4, "max_future_days": 30}

    # Gamificacao
    xp = db.Column(db.Integer, default=0)
    level = db.Column(db.Integer, default=1)
    xp_available = db.Column(db.Integer, default=0)
    credits_balance = db.Column(db.Integer, default=0)

    # Módulo de Vendas: origem do lead
    # Valores: 'quiz_organic' | 'referral' | 'admin_manual' | 'qr_code' | 'landing_page'
    lead_source = db.Column(db.String(50), nullable=True)

    # Status e Datas
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def is_instructor(self):
        return self.role in ['instructor', 'provider']

    def __repr__(self):
        return f'<User {self.name}>'
