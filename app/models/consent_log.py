# app/models/consent_log.py

from app import db
from datetime import datetime

class ConsentLog(db.Model):
    """
    Estrutura preparada para logs de consentimento (LGPD) futuros.
    Campos sugeridos: id, user_id, consent_type, accepted, ip_address, created_at
    """
    __tablename__ = 'consent_logs'
    id = db.Column(db.Integer, primary_key=True)
    pass
