# app/services/onboarding.py
"""
Lógica de negócio do módulo de Vendas & Onboarding.

Funções públicas:
    suggest_modalities        — sugere modalidades com base nas respostas do quiz
    filter_slots_by_turno     — filtra slots pelo turno do dia
    validate_demo_booking     — validações específicas para aulas demo
    suggest_demo_slots        — sugere slots para aula demo
    on_demo_completed         — trigger pós-checkin em booking_type='demo'
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from app import db
from app.models.booking import Booking, BookingStatus
from app.models.lead_profile import LeadProfile
from app.models.modality import Modality
from app.models.notification import Notification
from app.models.schedule_slot import ScheduleSlot

_DEMO_WINDOW_DAYS = 20
_TURNO_RANGES = {
    "manha": (time(6, 0),  time(12, 0)),
    "tarde": (time(12, 0), time(18, 0)),
    "noite": (time(18, 0), time(22, 0)),
}


# ---------------------------------------------------------------------------
# Quiz — Sugestão de Modalidades
# ---------------------------------------------------------------------------

def suggest_modalities(answers: dict) -> list[str]:
    """
    Retorna lista de modalidades sugeridas com base nas respostas do quiz.
    EZBody é sempre sugerido (exceto se PAR-Q reprovar depois).
    Musculação é adicionada conforme objetivo, tempo e frequência.
    """
    suggestions = ["ezbody"]

    objetivo  = answers.get("objetivo", "")
    tempo     = answers.get("tempo", "")
    frequencia = answers.get("frequencia", "")

    if objetivo in ["ganhar_massa", "manutencao"]:
        suggestions.append("musculacao")
    if tempo in ["30_60", "mais_60"] and "musculacao" not in suggestions:
        suggestions.append("musculacao")
    if frequencia in ["3_4x", "todos_dias"] and "musculacao" not in suggestions:
        suggestions.append("musculacao")

    return suggestions


# ---------------------------------------------------------------------------
# Turno — Filtro de Horários
# ---------------------------------------------------------------------------

def filter_slots_by_turno(slots: list, turno: str) -> list:
    """
    Filtra slots pelo turno desejado.
    'fds' filtra por fim de semana (weekday 5 ou 6).
    Outros turnos filtram por start_time.
    """
    if not turno:
        return slots
    if turno == "fds":
        return [s for s in slots if s.date.weekday() in (5, 6)]
    if turno in _TURNO_RANGES:
        start, end = _TURNO_RANGES[turno]
        return [s for s in slots if start <= s.start_time < end]
    return slots


# ---------------------------------------------------------------------------
# Demo Booking — Validação
# ---------------------------------------------------------------------------

def validate_demo_booking(client, slot: ScheduleSlot) -> Tuple[bool, Optional[str]]:
    """
    Validações específicas para booking_type='demo':
      1. slot.date <= hoje + 20 dias
      2. Slot ativo com vagas
      3. Nenhuma demo confirmed/completed do cliente na mesma modalidade
    Não verifica créditos (custo = 0 por definição).
    """
    today = date.today()

    if slot.date > today + timedelta(days=_DEMO_WINDOW_DAYS):
        return False, f"Aulas demonstrativas devem ser agendadas nos próximos {_DEMO_WINDOW_DAYS} dias."

    if slot.status != "active" or slot.available_spots <= 0:
        return False, "Este horário está indisponível."

    if slot.date < today:
        return False, "Não é possível agendar em datas passadas."

    existing = (
        Booking.query
        .join(ScheduleSlot)
        .filter(
            Booking.client_id == client.id,
            Booking.booking_type == "demo",
            Booking.status.in_([BookingStatus.CONFIRMED, BookingStatus.COMPLETED]),
            ScheduleSlot.modality_id == slot.modality_id,
        )
        .first()
    )
    if existing:
        return False, "Você já agendou uma aula demonstrativa desta modalidade."

    return True, None


# ---------------------------------------------------------------------------
# Demo — Sugestão de Slots Alternativos
# ---------------------------------------------------------------------------

def suggest_demo_slots(
    modality_id: int,
    turno: str,
    from_date: date,
    limit: int = 8,
) -> list[ScheduleSlot]:
    """
    Estratégia A: mesmo turno, qualquer dia dentro dos 20 dias.
    Estratégia B (fallback): qualquer turno, mais próximo da data preferida.
    Retorna slots ativos com vagas, ordenados por data ASC.
    """
    until = from_date + timedelta(days=_DEMO_WINDOW_DAYS)

    base_q = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.modality_id == modality_id,
            ScheduleSlot.date >= from_date,
            ScheduleSlot.date <= until,
            ScheduleSlot.status == "active",
        )
        .order_by(ScheduleSlot.date, ScheduleSlot.start_time)
    )

    candidates = base_q.all()
    # Remove full slots
    candidates = [s for s in candidates if s.available_spots > 0]

    # Strategy A — preferred turno
    if turno:
        filtered = filter_slots_by_turno(candidates, turno)
        if filtered:
            return filtered[:limit]

    # Strategy B — fallback: any turno
    return candidates[:limit]


# ---------------------------------------------------------------------------
# Trigger Pós-Demo Realizada
# ---------------------------------------------------------------------------

def on_demo_completed(booking: Booking) -> None:
    """
    Chamada quando provider faz checkin em booking com booking_type='demo'.
    Atualiza LeadProfile e cria notificação para admin.
    """
    if not booking or booking.booking_type != "demo":
        return

    lead = LeadProfile.query.filter_by(user_id=booking.client_id).first()
    if lead:
        lead.demo_booked_at  = datetime.utcnow()
        lead.onboarding_step = "demo_realizada"
        # não fazemos commit aqui — o caller (checkin) já faz
