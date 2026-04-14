# app/models/recurring_booking.py

from app import db
from datetime import datetime
import enum


class RecurringFrequency(enum.Enum):
    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"


class RecurringBooking(db.Model):
    """Série de agendamentos recorrentes."""
    __tablename__ = 'recurring_bookings'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    modality_id = db.Column(db.Integer, db.ForeignKey('modalities.id'), nullable=True)
    
    weekday = db.Column(db.Integer, nullable=False)   # 0=seg … 6=dom
    start_time = db.Column(db.Time, nullable=False)
    frequency = db.Column(db.Enum(RecurringFrequency), default=RecurringFrequency.WEEKLY)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True)
    
    valid_from = db.Column(db.Date, nullable=False)
    valid_until = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    client = db.relationship('User', backref='recurring_bookings_made', foreign_keys=[client_id])
    provider = db.relationship('User', backref='recurring_bookings_given', foreign_keys=[provider_id])
    modality = db.relationship('Modality', backref='recurring_bookings')

    def __repr__(self):
        return f'<RecurringBooking {self.id} - Client {self.client_id}>'
