# app/models/lead_profile.py
"""
Perfil de lead/onboarding — armazena respostas do quiz e estado da jornada.
"""

from datetime import datetime

from app import db


class LeadProfile(db.Model):
    """Estado completo da jornada de onboarding de um usuário."""
    __tablename__ = 'lead_profiles'

    id                   = db.Column(db.Integer, primary_key=True)
    user_id              = db.Column(db.Integer, db.ForeignKey('users.id'),
                                     nullable=False, unique=True)

    # Respostas do quiz
    objetivo             = db.Column(db.String(50), nullable=True)
    tempo_disponivel     = db.Column(db.String(20), nullable=True)
    frequencia           = db.Column(db.String(20), nullable=True)
    experiencia          = db.Column(db.String(20), nullable=True)
    turno                = db.Column(db.String(20), nullable=True)

    # Resultado da sugestão
    modalities_suggested = db.Column(db.JSON, nullable=True)   # ['ezbody', 'musculacao']

    # Triagem EZBody (PAR-Q)
    parq_passed          = db.Column(db.Boolean, nullable=True)
    parq_answers         = db.Column(db.JSON, nullable=True)

    # Marcos da jornada
    quiz_completed_at    = db.Column(db.DateTime, nullable=True)
    demo_booked_at       = db.Column(db.DateTime, nullable=True)
    converted_at         = db.Column(db.DateTime, nullable=True)

    # Passo atual do funil
    # Valores: 'quiz' | 'suggestion' | 'parq' | 'booking' | 'confirmed' | 'demo_realizada' | 'converted'
    onboarding_step      = db.Column(db.String(30), default='quiz', nullable=False)

    created_at           = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at           = db.Column(db.DateTime, default=datetime.utcnow,
                                     onupdate=datetime.utcnow)

    user = db.relationship('User', backref=db.backref('lead_profile', uselist=False))

    def __repr__(self):
        return f'<LeadProfile user={self.user_id} step={self.onboarding_step}>'
