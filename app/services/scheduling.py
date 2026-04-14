# app/services/scheduling.py
"""
Motor de agendamento — lógica de negócio crítica.

Funções públicas:
    generate_slots_from_template  — gera ScheduleSlots a partir de um template
    validate_booking              — valida se um cliente pode agendar um slot
    suggest_alternatives          — sugere slots alternativos quando um está indisponível
    create_recurring_bookings     — cria bookings para toda uma série recorrente
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import List, Optional, Tuple

from app import db
from app.models.booking import Booking, BookingStatus
from app.models.recurring_booking import RecurringBooking, RecurringFrequency
from app.models.schedule_slot import ScheduleSlot
from app.models.schedule_template import ScheduleTemplate

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_DEFAULT_GENERATION_DAYS = 30   # dias para frente quando valid_until é None
_ALTERNATIVES_DATE_WINDOW = 3   # ±dias para busca de alternativas na mesma hora
_ALTERNATIVES_LIMIT = 5
_MAX_RECURRENCE_DAYS = 730      # guarda contra loops infinitos (≈ 2 anos)

# ---------------------------------------------------------------------------
# Helpers privados
# ---------------------------------------------------------------------------


def _add_minutes(t: time, minutes: int) -> time:
    """Soma `minutes` a um objeto :class:`datetime.time`."""
    dt = datetime.combine(date.today(), t) + timedelta(minutes=minutes)
    return dt.time()


def _get_policy(provider) -> dict:
    """
    Lê schedule_policy_json do prestador aplicando defaults seguros.

    Defaults:
        min_notice_hours    = 2
        cancel_deadline_hours = 4
        max_future_days     = 30
    """
    defaults: dict = {
        "min_notice_hours": 2,
        "cancel_deadline_hours": 4,
        "max_future_days": 30,
    }
    if provider and provider.schedule_policy_json:
        return {**defaults, **provider.schedule_policy_json}
    return defaults


def _next_weekday_from(from_date: date, weekday: int) -> date:
    """
    Retorna a primeira data >= `from_date` que caia no `weekday` informado.
    Convenção do PRD: 0 = segunda, 6 = domingo (igual a `date.weekday()`).
    """
    days_ahead = (weekday - from_date.weekday()) % 7
    return from_date + timedelta(days=days_ahead)


# ---------------------------------------------------------------------------
# 1. Geração de Slots a partir de Template
# ---------------------------------------------------------------------------


def generate_slots_from_template(
    template: ScheduleTemplate,
    until: Optional[date] = None,
) -> List[ScheduleSlot]:
    """
    Percorre o intervalo ``[template.valid_from, end_date]`` e cria um
    :class:`ScheduleSlot` para cada combinação (dia × horário) definida
    no template, sem duplicar slots já existentes.

    Critério de unicidade: ``(provider_id, date, start_time)``.

    Parâmetros
    ----------
    template:
        Template de disponibilidade do prestador.
    until:
        Forçar data limite (substitui `template.valid_until`).
        Útil para testes ou para limitar a geração pontual.

    Retorna
    -------
    Lista dos :class:`ScheduleSlot` efetivamente criados nesta chamada.
    O caller é responsável pelo ``db.session.commit()``.
    """
    # --- Janela de geração ---
    start_date: date = template.valid_from

    if until is not None:
        end_date = until
    elif template.valid_until is not None:
        end_date = template.valid_until
    else:
        end_date = start_date + timedelta(days=_DEFAULT_GENERATION_DAYS)

    # --- Pré-carregar slots existentes em memória para deduplicação eficiente ---
    existing: set[tuple[date, time]] = {
        (s.date, s.start_time)
        for s in ScheduleSlot.query.filter(
            ScheduleSlot.provider_id == template.provider_id,
            ScheduleSlot.date >= start_date,
            ScheduleSlot.date <= end_date,
        ).all()
    }

    created: List[ScheduleSlot] = []
    current_date = start_date

    while current_date <= end_date:
        # date.weekday(): Mon=0 … Sun=6 — mesma convenção do PRD
        if current_date.weekday() in template.weekdays:
            cursor_time: time = template.start_time

            while True:
                slot_end: time = _add_minutes(cursor_time, template.slot_duration_min)

                # Parar quando o próximo slot ultrapassaria o fim do expediente
                if slot_end > template.end_time:
                    break

                if (current_date, cursor_time) not in existing:
                    slot = ScheduleSlot(
                        provider_id=template.provider_id,
                        template_id=template.id,
                        modality_id=template.modality_id,
                        date=current_date,
                        start_time=cursor_time,
                        end_time=slot_end,
                        max_capacity=template.max_capacity,
                        status="active",
                    )
                    db.session.add(slot)
                    existing.add((current_date, cursor_time))
                    created.append(slot)

                cursor_time = slot_end
                if cursor_time >= template.end_time:
                    break

        current_date += timedelta(days=1)

    # flush para atribuir IDs sem fechar a transação — o caller decide o commit
    db.session.flush()
    return created


# ---------------------------------------------------------------------------
# 2. Validação de Booking
# ---------------------------------------------------------------------------


def validate_booking(
    client,
    slot: ScheduleSlot,
    subscription=None,
) -> Tuple[bool, Optional[str]]:
    """
    Verifica se `client` pode criar um :class:`Booking` no `slot`.

    Checagens (em ordem):

    1. Slot está ativo (não cancelado nem lotado pelo sistema)
    2. Há vagas disponíveis
    3. Data do slot não é passado
    4. Antecedência mínima respeitada (``min_notice_hours`` da política do prestador)
    5. Slot está dentro da janela máxima de agendamento futuro
    6. Cliente não está inscrito neste slot (booking ``confirmed`` existente)
    7. [Opcional] Assinatura tem créditos suficientes

    Retorna
    -------
    ``(True, None)``
        Booking permitido.
    ``(False, mensagem)``
        Booking bloqueado; mensagem em pt-BR pronta para exibição ao usuário.
    """
    policy = _get_policy(slot.provider)
    now = datetime.utcnow()
    today = now.date()

    # 1. Slot ativo
    if slot.status != "active":
        status_labels = {"cancelled": "cancelado", "full": "lotado"}
        label = status_labels.get(slot.status, "indisponível")
        return False, f"Este horário está {label}."

    # 2. Vagas disponíveis
    if slot.available_spots <= 0:
        return False, "Este horário está lotado."

    # 3. Data no futuro
    if slot.date < today:
        return False, "Não é possível agendar em datas passadas."

    # 4. Antecedência mínima
    min_notice: int = policy.get("min_notice_hours", 0)
    if min_notice:
        slot_datetime = datetime.combine(slot.date, slot.start_time)
        earliest_allowed = now + timedelta(hours=min_notice)
        if slot_datetime < earliest_allowed:
            return False, (
                f"Agendamentos devem ser feitos com pelo menos "
                f"{min_notice}h de antecedência."
            )

    # 5. Janela máxima de agendamento futuro
    max_future: int = policy.get("max_future_days", 365)
    if slot.date > today + timedelta(days=max_future):
        return False, (
            f"Só é possível agendar com até {max_future} dias de antecedência."
        )

    # 6. Duplo booking
    already_booked = Booking.query.filter_by(
        client_id=client.id,
        slot_id=slot.id,
        status=BookingStatus.CONFIRMED,
    ).first()
    if already_booked:
        return False, "Você já possui um agendamento neste horário."

    # 7. Créditos (somente se subscription foi fornecida)
    if subscription is not None:
        credits_cost = slot.modality.credits_cost if slot.modality else 1
        if subscription.credits_remaining < credits_cost:
            return False, (
                f"Créditos insuficientes. "
                f"Este horário custa {credits_cost} crédito(s) e você possui "
                f"{subscription.credits_remaining}."
            )

    return True, None


# ---------------------------------------------------------------------------
# 3. Sugestão de Alternativos
# ---------------------------------------------------------------------------


def suggest_alternatives(
    slot: ScheduleSlot,
    limit: int = _ALTERNATIVES_LIMIT,
) -> List[ScheduleSlot]:
    """
    Retorna até `limit` slots alternativos quando `slot` está indisponível,
    ordenados por menor distância temporal ao horário original.

    Estratégia:

    **A)** Mesmo prestador + mesmo ``start_time`` em datas ±3 dias.
    **B)** Mesmo prestador + horários diferentes no mesmo dia.

    Apenas slots com ``status == 'active'`` e ``available_spots > 0``
    são incluídos. Datas passadas são ignoradas.
    """
    today = date.today()
    candidates: List[ScheduleSlot] = []
    seen_ids: set[int] = {slot.id}

    # --- A) Mesmo horário em datas próximas ---
    for delta in range(1, _ALTERNATIVES_DATE_WINDOW + 1):
        for sign in (-1, 1):
            target_date = slot.date + timedelta(days=sign * delta)
            if target_date < today:
                continue

            alt = (
                ScheduleSlot.query
                .filter(
                    ScheduleSlot.provider_id == slot.provider_id,
                    ScheduleSlot.date == target_date,
                    ScheduleSlot.start_time == slot.start_time,
                    ScheduleSlot.status == "active",
                )
                .first()
            )
            if alt and alt.id not in seen_ids and alt.available_spots > 0:
                candidates.append(alt)
                seen_ids.add(alt.id)

    # --- B) Horários diferentes no mesmo dia (mesmo prestador) ---
    same_day_slots = (
        ScheduleSlot.query
        .filter(
            ScheduleSlot.provider_id == slot.provider_id,
            ScheduleSlot.date == slot.date,
            ScheduleSlot.status == "active",
        )
        .all()
    )
    for alt in same_day_slots:
        if alt.id not in seen_ids and alt.available_spots > 0:
            candidates.append(alt)
            seen_ids.add(alt.id)

    # --- Ordenar por distância temporal ao slot original ---
    origin_dt = datetime.combine(slot.date, slot.start_time)
    candidates.sort(
        key=lambda s: abs(
            (datetime.combine(s.date, s.start_time) - origin_dt).total_seconds()
        )
    )

    return candidates[:limit]


# ---------------------------------------------------------------------------
# 4. Processamento de Recorrência
# ---------------------------------------------------------------------------


def create_recurring_bookings(
    recurring: RecurringBooking,
    subscription=None,
) -> Tuple[List[Booking], List[date]]:
    """
    Cria :class:`Booking` para todas as ocorrências futuras de uma série
    recorrente, respeitando disponibilidade e políticas do prestador.

    Algoritmo:

    1. Calcula a primeira ocorrência >= max(valid_from, hoje)
    2. Busca o :class:`ScheduleSlot` correspondente
       (provider_id + date + start_time + status='active')
    3. Valida o booking via :func:`validate_booking`
    4. Se válido → cria :class:`Booking` vinculado à série
    5. Se inválido → registra a data na lista de conflitos
    6. Avança `step_days` dias (7 para semanal, 14 para quinzenal)

    Parâmetros
    ----------
    recurring:
        Série de agendamentos recorrentes já persistida no banco.
    subscription:
        Assinatura a ser debitada. Pode ser ``None`` se o prestador não
        exige créditos.

    Retorna
    -------
    ``(criados, conflitos)``
        - ``criados``  — lista de :class:`Booking` adicionados à sessão
        - ``conflitos`` — lista de datas sem slot disponível ou sem vaga

    O caller é responsável pelo ``db.session.commit()``.
    """
    today = date.today()
    start = max(recurring.valid_from, today)
    end: Optional[date] = recurring.valid_until

    step_days = 7 if recurring.frequency == RecurringFrequency.WEEKLY else 14

    created: List[Booking] = []
    conflicts: List[date] = []

    current = _next_weekday_from(start, recurring.weekday)
    cutoff = today + timedelta(days=_MAX_RECURRENCE_DAYS)

    while (end is None or current <= end) and current <= cutoff:
        slot: Optional[ScheduleSlot] = (
            ScheduleSlot.query
            .filter_by(
                provider_id=recurring.provider_id,
                date=current,
                start_time=recurring.start_time,
                status="active",
            )
            .first()
        )

        if slot:
            ok, _ = validate_booking(recurring.client, slot, subscription)
            if ok:
                credits_cost = slot.modality.credits_cost if slot.modality else 1
                booking = Booking(
                    client_id=recurring.client_id,
                    slot_id=slot.id,
                    subscription_id=recurring.subscription_id,
                    recurring_id=recurring.id,
                    status=BookingStatus.CONFIRMED,
                    cost_at_booking=credits_cost,
                )
                db.session.add(booking)
                created.append(booking)
            else:
                conflicts.append(current)
        else:
            conflicts.append(current)

        current += timedelta(days=step_days)

    db.session.flush()
    return created, conflicts
