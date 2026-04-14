# app/models/workout_log.py

from app import db
from datetime import datetime

class WorkoutLog(db.Model):
    """
    Estrutura preparada para logs de treino futuros.
    Campos sugeridos: id, user_id, session_exercise_id, sets_done, reps_done, weight_kg, date, notes
    """
    __tablename__ = 'workout_logs'
    id = db.Column(db.Integer, primary_key=True)
    pass
