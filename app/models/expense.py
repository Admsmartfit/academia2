# app/models/expense.py

from app import db
from datetime import datetime

class Expense(db.Model):
    """
    Estrutura preparada para despesas futuras.
    Campos sugeridos: id, description, category, amount, date, is_recurring, created_by_id
    """
    __tablename__ = 'expenses'
    id = db.Column(db.Integer, primary_key=True)
    pass
