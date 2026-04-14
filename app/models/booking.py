# app/models/booking.py

from app import db
from datetime import datetime
import enum


class BookingStatus(enum.Enum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    NO_SHOW = "no_show"


class Booking(db.Model):
    """Reserva de um cliente em um slot. Modelo central."""
    __tablename__ = 'bookings'

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    slot_id = db.Column(db.Integer, db.ForeignKey('schedule_slots.id'), nullable=False)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True)
    recurring_id = db.Column(db.Integer, db.ForeignKey('recurring_bookings.id'), nullable=True)
    
    status = db.Column(db.Enum(BookingStatus), default=BookingStatus.CONFIRMED)
    cost_at_booking = db.Column(db.Integer, nullable=False, default=0)  # créditos debitados
    
    booked_at = db.Column(db.DateTime, default=datetime.utcnow)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    cancel_reason = db.Column(db.String(255), nullable=True)
    checked_in_at = db.Column(db.DateTime, nullable=True)
    xp_awarded = db.Column(db.Integer, default=0)

    # Relacionamentos
    client = db.relationship('User', backref='bookings_made', foreign_keys=[client_id])
    slot = db.relationship('ScheduleSlot', backref='bookings')

    def __repr__(self):
        return f'<Booking {self.id} - Client {self.client_id} - Slot {self.slot_id}>'
