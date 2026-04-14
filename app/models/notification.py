# app/models/notification.py

from app import db
from datetime import datetime

class Notification(db.Model):
    """
    Estrutura preparada para notificações futuras.
    Campos sugeridos: id, user_id, type, title, message, is_read, created_at
    """
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    pass
