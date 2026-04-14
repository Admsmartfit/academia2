# app/models/audit_log.py

from app import db
from datetime import datetime

class AuditLog(db.Model):
    """
    Estrutura preparada para logs de auditoria futuros.
    Campos sugeridos: id, user_id, action, entity_type, entity_id, old_value, new_value, created_at
    """
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    pass
