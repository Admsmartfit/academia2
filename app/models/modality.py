# app/models/modality.py

from app import db
from datetime import datetime


class Modality(db.Model):
    __tablename__ = 'modalities'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    color = db.Column(db.String(7), default='#FF6B35')
    icon = db.Column(db.String(50))
    is_active = db.Column(db.Boolean, default=True)
    
    # Campos atualizados conforme PRD
    credits_cost = db.Column(db.Integer, default=1, nullable=False)
    slot_duration_min = db.Column(db.Integer, default=60, nullable=False)
    
    is_featured = db.Column(db.Boolean, default=False)
    requires_gender_segregation = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Modality {self.name}>'
