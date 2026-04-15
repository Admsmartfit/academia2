# app/services/__init__.py
from app.services.scheduling import (
    generate_slots_from_template,
    validate_booking,
    suggest_alternatives,
    create_recurring_bookings,
)

from app.services.onboarding import (
    suggest_modalities,
    filter_slots_by_turno,
    validate_demo_booking,
    suggest_demo_slots,
    on_demo_completed,
)

__all__ = [
    "generate_slots_from_template",
    "validate_booking",
    "suggest_alternatives",
    "create_recurring_bookings",
    "suggest_modalities",
    "filter_slots_by_turno",
    "validate_demo_booking",
    "suggest_demo_slots",
    "on_demo_completed",
]
