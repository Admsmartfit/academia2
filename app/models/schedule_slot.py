# app/models/schedule_slot.py

from app import db
from datetime import datetime


class ScheduleSlot(db.Model):
    """Horário concreto gerado a partir de um template ou criado avulsamente."""
    __tablename__ = 'schedule_slots'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    template_id = db.Column(db.Integer, db.ForeignKey('schedule_templates.id'), nullable=True)
    modality_id = db.Column(db.Integer, db.ForeignKey('modalities.id'), nullable=True)
    
    date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_capacity = db.Column(db.Integer, nullable=False)
    
    status = db.Column(db.Enum('active', 'cancelled', 'full', name='slot_status'), default='active')
    cancel_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    provider = db.relationship('User', backref='slots')
    template = db.relationship('ScheduleTemplate', backref='slots')
    modality = db.relationship('Modality', backref='slots')

    # Computed properties
    @property
    def booked_count(self):
        from app.models.booking import Booking, BookingStatus
        return Booking.query.filter_by(slot_id=self.id, status=BookingStatus.CONFIRMED).count()

    @property
    def available_spots(self):
        return self.max_capacity - self.booked_count

    @property
    def occupancy_pct(self):
        """Calcula a taxa de ocupação: (booked_count * 100) / capacity"""
        if not self.max_capacity:
            return 0
        return (self.booked_count * 100) / self.max_capacity

    def __repr__(self):
        return f'<ScheduleSlot {self.date} {self.start_time} - Provider {self.provider_id}>'
