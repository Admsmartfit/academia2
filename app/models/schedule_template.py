# app/models/schedule_template.py

from app import db
from datetime import datetime


class ScheduleTemplate(db.Model):
    """Define as regras de disponibilidade semanal do prestador."""
    __tablename__ = 'schedule_templates'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    modality_id = db.Column(db.Integer, db.ForeignKey('modalities.id'), nullable=True)
    
    weekdays = db.Column(db.JSON, nullable=False)     # [0,1,2,3,4] = seg a sex
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    slot_duration_min = db.Column(db.Integer, nullable=False, default=60)
    max_capacity = db.Column(db.Integer, nullable=False, default=10)
    
    valid_from = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=True)      # null = indeterminado
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    provider = db.relationship('User', backref='schedule_templates')
    modality = db.relationship('Modality', backref='schedule_templates')

    def __repr__(self):
        return f'<ScheduleTemplate {self.id} - Provider {self.provider_id}>'
