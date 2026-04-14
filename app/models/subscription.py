# app/models/subscription.py
"""
Modelo de assinatura do aluno.
Stub funcional para o módulo de agendamento.
Será expandido nas etapas financeiras do PRD.
"""

from app import db
from datetime import datetime, date
import enum


class SubscriptionStatus(enum.Enum):
    ACTIVE    = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED   = "expired"


class Subscription(db.Model):
    __tablename__ = "subscriptions"

    id             = db.Column(db.Integer, primary_key=True)
    user_id        = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name           = db.Column(db.String(100), nullable=False, default="Plano")
    credits_total  = db.Column(db.Integer, nullable=False, default=0)
    credits_used   = db.Column(db.Integer, nullable=False, default=0)
    start_date     = db.Column(db.Date, nullable=False, default=date.today)
    end_date       = db.Column(db.Date, nullable=False, default=date.today)
    status         = db.Column(
        db.Enum(SubscriptionStatus), default=SubscriptionStatus.ACTIVE, nullable=False
    )
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # Relacionamentos
    user = db.relationship("User", backref="subscriptions")

    # ------------------------------------------------------------------
    # Propriedades computadas
    # ------------------------------------------------------------------

    @property
    def credits_remaining(self) -> int:
        return max(0, self.credits_total - self.credits_used)

    @property
    def is_active(self) -> bool:
        return (
            self.status == SubscriptionStatus.ACTIVE
            and self.end_date >= date.today()
            and self.credits_remaining > 0
        )

    @property
    def days_until_expiry(self) -> int:
        return (self.end_date - date.today()).days

    # ------------------------------------------------------------------
    # Métodos de negócio
    # ------------------------------------------------------------------

    def use_credit(self, amount: int = 1) -> None:
        """Debita créditos da assinatura."""
        self.credits_used = min(self.credits_total, self.credits_used + amount)

    def refund_credit(self, amount: int = 1) -> None:
        """Estorna créditos para a assinatura."""
        self.credits_used = max(0, self.credits_used - amount)

    def __repr__(self) -> str:
        return f"<Subscription {self.name} · {self.credits_remaining} créditos>"
