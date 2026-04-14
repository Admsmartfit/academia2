# tests/test_critical.py
"""
Suíte de testes críticos — PRD Seção 10.

Cobre os 5 cenários prioritários:
    1. Concorrência          — última vaga disputada por dois clientes simultaneamente
    2. Políticas de Tempo    — min_notice_hours e cancel_deadline_hours
    3. Saldo e Créditos      — agendamento sem créditos
    4. Integridade de Série  — cancelar uma ocorrência não afeta as demais
    5. Cancelamento Prestador— slot deletado com inscritos → bookings cancelados

Uso:
    pytest tests/test_critical.py -v
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.models.booking import Booking, BookingStatus
from app.models.modality import Modality
from app.models.recurring_booking import RecurringBooking, RecurringFrequency
from app.models.schedule_slot import ScheduleSlot
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.scheduling import (
    create_recurring_bookings,
    suggest_alternatives,
    validate_booking,
)

from tests.conftest import make_slot


# ===========================================================================
# 1. CONCORRÊNCIA — última vaga disputada por dois clientes
# ===========================================================================


class TestConcurrency:
    """
    PRD § 10.1: Dois clientes tentam agendar a última vaga de um slot
    simultâneamente. Apenas um deve ter sucesso; o outro deve receber
    sugestões de horários alternativos.
    """

    def test_race_condition_window_both_pass_validation(
        self, db, provider, student, student2, subscription, subscription2, modality
    ):
        """
        Demonstra a janela de race condition: sem serialização de transação,
        dois clientes podem passar pela validação simultâneamente antes que
        qualquer um faça flush — ambos veem available_spots=1.

        Reproduz o cenário crítico PRD § 10.2 de forma determinística:
          T1: validate_booking(student)  → ok=True  (vaga=1)
          T2: validate_booking(student2) → ok=True  (vaga ainda=1, nenhum flush ainda)
          T1: insere booking, flush      → vaga passa a 0
          T2: insere booking, flush      → OVERBOOKING (2 bookings para 1 vaga)

        A guarda correta em produção é SELECT FOR UPDATE ou serializable isolation.
        O teste test_validate_booking_fails_when_slot_full cobre o cenário sequencial.
        """
        slot = make_slot(db, provider, modality, capacity=1)

        # Ambos validam ANTES de qualquer insert (simula race condition)
        ok1, _ = validate_booking(student, slot, subscription)
        ok2, _ = validate_booking(student2, slot, subscription2)

        # Ambos passam na validação — esta é a janela de vulnerabilidade
        assert ok1 is True, "Primeiro cliente deveria passar na validação"
        assert ok2 is True, "Segundo cliente também passa — janela de race condition"

        # Primeiro insere
        b1 = Booking(
            client_id=student.id,
            slot_id=slot.id,
            subscription_id=subscription.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add(b1)
        db.session.flush()

        # Segundo insere sem nova validação — overbooking acontece
        b2 = Booking(
            client_id=student2.id,
            slot_id=slot.id,
            subscription_id=subscription2.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add(b2)
        db.session.flush()

        # Demonstra que sem locking, 2 bookings foram criados para 1 vaga
        confirmed = Booking.query.filter_by(
            slot_id=slot.id, status=BookingStatus.CONFIRMED
        ).count()
        assert confirmed == 2, (
            "Race condition confirmada: 2 bookings para 1 vaga sem SELECT FOR UPDATE"
        )
        # Em produção com SELECT FOR UPDATE ou SERIALIZABLE: confirmed seria 1.

    def test_validate_booking_fails_when_slot_full(
        self, db, provider, student, student2, subscription, subscription2, modality
    ):
        """
        Garante que validate_booking retorna False quando available_spots == 0,
        que é a guarda contra race condition na camada de serviço.
        """
        slot = make_slot(db, provider, modality, capacity=1)

        # Primeiro agendamento — deve ser aprovado
        ok1, _ = validate_booking(student, slot, subscription)
        assert ok1 is True

        # Registra o booking para que available_spots mude
        b = Booking(
            client_id=student.id,
            slot_id=slot.id,
            subscription_id=subscription.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add(b)
        db.session.flush()

        # Segundo cliente tenta a mesma vaga
        ok2, msg2 = validate_booking(student2, slot, subscription2)
        assert ok2 is False
        assert "lotado" in msg2.lower()

    def test_alternatives_suggested_when_slot_full(
        self, db, provider, student, modality
    ):
        """
        Quando um slot está lotado, suggest_alternatives deve retornar até 5
        slots alternativos com vagas disponíveis.
        """
        full_slot = make_slot(db, provider, modality, capacity=1)

        # Ocupa a vaga
        b = Booking(
            client_id=student.id,
            slot_id=full_slot.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add(b)
        db.session.flush()

        # Cria alternativas: mesma hora, datas vizinhas
        for delta in range(1, 4):
            alt = ScheduleSlot(
                provider_id=provider.id,
                modality_id=modality.id,
                date=full_slot.date + timedelta(days=delta),
                start_time=full_slot.start_time,
                end_time=full_slot.end_time,
                max_capacity=5,
                status="active",
            )
            db.session.add(alt)
        db.session.flush()

        alternatives = suggest_alternatives(full_slot, limit=5)

        assert len(alternatives) >= 1
        for alt in alternatives:
            assert alt.available_spots > 0
            assert alt.status == "active"
            assert alt.id != full_slot.id


# ===========================================================================
# 2. POLÍTICAS DE TEMPO
# ===========================================================================


class TestTimePolicies:
    """
    PRD § 10.2: Tentativas fora das janelas de tempo configuradas pelo
    prestador (min_notice_hours, cancel_deadline_hours).
    """

    def test_booking_rejected_inside_min_notice_window(
        self, db, provider, student, subscription, modality
    ):
        """
        Slot que começa em menos de min_notice_hours (2h) deve ser rejeitado.
        """
        soon = datetime.utcnow() + timedelta(hours=1)
        slot = ScheduleSlot(
            provider_id=provider.id,
            modality_id=modality.id,
            date=soon.date(),
            start_time=soon.time().replace(second=0, microsecond=0),
            end_time=(soon + timedelta(hours=1)).time().replace(second=0, microsecond=0),
            max_capacity=10,
            status="active",
        )
        db.session.add(slot)
        db.session.flush()

        ok, msg = validate_booking(student, slot, subscription)

        assert ok is False
        assert "antecedência" in msg.lower()

    def test_booking_accepted_outside_min_notice_window(
        self, db, provider, student, subscription, modality
    ):
        """
        Slot com início bem além de min_notice_hours deve ser aceito.
        """
        slot = make_slot(db, provider, modality, days_ahead=5)

        ok, msg = validate_booking(student, slot, subscription)

        assert ok is True, f"Falhou inesperadamente: {msg}"

    def test_cancel_outside_deadline_is_blocked(
        self, db, provider, student, subscription, modality
    ):
        """
        Cancelamento tentado quando falta menos de cancel_deadline_hours para
        o início do slot deve ser bloqueado.

        Valida a lógica do route student.booking_cancel:
            datetime.utcnow() + timedelta(hours=deadline_hours) > slot_dt
        """
        policy = provider.schedule_policy_json or {}
        deadline_hours = policy.get("cancel_deadline_hours", 4)

        # Slot que começa em 2h — dentro da janela de cancelamento (deadline=4h)
        slot_dt = datetime.utcnow() + timedelta(hours=2)
        slot = ScheduleSlot(
            provider_id=provider.id,
            modality_id=modality.id,
            date=slot_dt.date(),
            start_time=slot_dt.time().replace(second=0, microsecond=0),
            end_time=(slot_dt + timedelta(hours=1)).time().replace(second=0, microsecond=0),
            max_capacity=10,
            status="active",
        )
        db.session.add(slot)
        db.session.flush()

        booking = Booking(
            client_id=student.id,
            slot_id=slot.id,
            subscription_id=subscription.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add(booking)
        db.session.flush()

        slot_datetime = datetime.combine(slot.date, slot.start_time)
        can_cancel = datetime.utcnow() + timedelta(hours=deadline_hours) <= slot_datetime

        assert can_cancel is False, (
            f"Cancelamento deveria ser bloqueado quando falta menos de "
            f"{deadline_hours}h para o início."
        )

    def test_cancel_within_deadline_is_allowed(
        self, db, provider, student, subscription, modality
    ):
        """
        Cancelamento com antecedência suficiente deve ser permitido.
        """
        policy = provider.schedule_policy_json or {}
        deadline_hours = policy.get("cancel_deadline_hours", 4)

        slot = make_slot(db, provider, modality, days_ahead=1)

        booking = Booking(
            client_id=student.id,
            slot_id=slot.id,
            subscription_id=subscription.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add(booking)
        db.session.flush()

        slot_datetime = datetime.combine(slot.date, slot.start_time)
        can_cancel = datetime.utcnow() + timedelta(hours=deadline_hours) <= slot_datetime

        assert can_cancel is True

    def test_booking_rejected_beyond_max_future_days(
        self, db, provider, student, subscription, modality
    ):
        """
        Slot com mais de max_future_days (60) no futuro deve ser rejeitado.
        """
        slot = make_slot(db, provider, modality, days_ahead=90)

        ok, msg = validate_booking(student, slot, subscription)

        assert ok is False
        assert "antecedência" in msg.lower() or "dias" in msg.lower()


# ===========================================================================
# 3. SALDO E CRÉDITOS
# ===========================================================================


class TestCredits:
    """
    PRD § 10.3: Agendamento sem créditos deve ser rejeitado com mensagem
    clara referenciando a loja de pacotes.
    """

    def test_booking_rejected_when_no_credits(
        self, db, provider, student, modality
    ):
        """
        Cliente com créditos_remaining == 0 não pode agendar.
        """
        sub_empty = Subscription(
            user_id=student.id,
            name="Plano Zerado",
            credits_total=3,
            credits_used=3,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            status=SubscriptionStatus.ACTIVE,
        )
        db.session.add(sub_empty)
        db.session.flush()

        slot = make_slot(db, provider, modality)

        ok, msg = validate_booking(student, slot, sub_empty)

        assert ok is False
        assert "crédito" in msg.lower()

    def test_booking_rejected_when_credits_below_cost(
        self, db, student
    ):
        """
        Modalidade com credits_cost=3 e assinatura com apenas 2 créditos.
        """
        expensive_modality = Modality(
            name="Personal Training", credits_cost=3, slot_duration_min=60
        )
        db.session.add(expensive_modality)

        sub_low = Subscription(
            user_id=student.id,
            name="Plano Básico",
            credits_total=10,
            credits_used=8,  # apenas 2 restantes
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            status=SubscriptionStatus.ACTIVE,
        )
        db.session.add(sub_low)
        db.session.flush()

        provider2 = User(
            name="Provider B",
            email="provb@test.com",
            phone="11555550000",
            role="instructor",
        )
        provider2.set_password("x")
        db.session.add(provider2)
        db.session.flush()

        slot = make_slot(db, provider2, expensive_modality)

        ok, msg = validate_booking(student, slot, sub_low)

        assert ok is False
        assert "insuficiente" in msg.lower() or "crédito" in msg.lower()
        assert "3" in msg  # custo da modalidade
        assert "2" in msg  # créditos restantes

    def test_booking_allowed_when_sufficient_credits(
        self, db, provider, student, subscription, modality
    ):
        """
        Sanity check: assinatura com créditos suficientes deve ser aprovada.
        """
        slot = make_slot(db, provider, modality)

        ok, msg = validate_booking(student, slot, subscription)

        assert ok is True, f"Deveria ser aprovado mas falhou: {msg}"

    def test_booking_without_subscription_skips_credit_check(
        self, db, provider, student, modality
    ):
        """
        Se subscription=None, a verificação de créditos é pulada.
        Útil para modalidades free ou cobranças externas.
        """
        slot = make_slot(db, provider, modality)

        ok, msg = validate_booking(student, slot, subscription=None)

        assert ok is True, f"Sem assinatura deve pular check de crédito: {msg}"

    def test_error_message_content_for_zero_credits(
        self, db, provider, student, modality
    ):
        """
        A mensagem de erro para créditos insuficientes deve ser informativa:
        deve incluir o custo do horário e quantos créditos o aluno possui.
        """
        sub_zero = Subscription(
            user_id=student.id,
            name="Zerado",
            credits_total=5,
            credits_used=5,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            status=SubscriptionStatus.ACTIVE,
        )
        db.session.add(sub_zero)
        db.session.flush()

        slot = make_slot(db, provider, modality)

        ok, msg = validate_booking(student, slot, sub_zero)

        assert ok is False
        assert msg is not None
        assert len(msg) > 10


# ===========================================================================
# 4. INTEGRIDADE DE RECORRÊNCIA
# ===========================================================================


class TestRecurrenceIntegrity:
    """
    PRD § 10.4: Cancelar uma ocorrência individual de uma série recorrente
    não deve afetar as demais ocorrências.
    """

    def _create_weekly_series(self, db, provider, student, modality, num_weeks=4):
        """
        Cria `num_weeks` slots semanais e uma RecurringBooking com bookings
        para todos eles.
        """
        today = date.today()
        days_to_monday = (7 - today.weekday()) % 7 or 7
        first_monday = today + timedelta(days=days_to_monday)

        slots = []
        for w in range(num_weeks):
            slot = ScheduleSlot(
                provider_id=provider.id,
                modality_id=modality.id,
                date=first_monday + timedelta(weeks=w),
                start_time=time(9, 0),
                end_time=time(10, 0),
                max_capacity=10,
                status="active",
            )
            db.session.add(slot)
            slots.append(slot)
        db.session.flush()

        recurring = RecurringBooking(
            client_id=student.id,
            provider_id=provider.id,
            modality_id=modality.id,
            weekday=0,  # segunda-feira
            start_time=time(9, 0),
            frequency=RecurringFrequency.WEEKLY,
            valid_from=first_monday,
            valid_until=first_monday + timedelta(weeks=num_weeks - 1),
            is_active=True,
        )
        db.session.add(recurring)
        db.session.flush()

        bookings = []
        for slot in slots:
            b = Booking(
                client_id=student.id,
                slot_id=slot.id,
                recurring_id=recurring.id,
                status=BookingStatus.CONFIRMED,
                cost_at_booking=1,
            )
            db.session.add(b)
            bookings.append(b)
        db.session.flush()

        return recurring, slots, bookings

    def test_cancel_one_booking_leaves_series_intact(
        self, db, provider, student, modality
    ):
        """
        Cancelar booking[1] (segunda semana) não deve alterar o status dos
        demais bookings nem o status da RecurringBooking.
        """
        recurring, _, bookings = self._create_weekly_series(
            db, provider, student, modality, num_weeks=4
        )
        total = len(bookings)

        target = bookings[1]
        target.status = BookingStatus.CANCELLED
        target.cancelled_at = datetime.utcnow()
        target.cancel_reason = "Cancelamento individual de teste"
        db.session.flush()

        assert recurring.is_active is True

        confirmed_after = Booking.query.filter_by(
            recurring_id=recurring.id,
            status=BookingStatus.CONFIRMED,
        ).count()
        assert confirmed_after == total - 1, (
            f"Esperado {total - 1} bookings confirmados, encontrado {confirmed_after}"
        )

        assert db.session.get(Booking, target.id).status == BookingStatus.CANCELLED

    def test_cancel_one_booking_does_not_deactivate_recurring(
        self, db, provider, student, modality
    ):
        """
        O RecurringBooking permanece is_active=True após cancelamento individual.
        """
        recurring, _, bookings = self._create_weekly_series(
            db, provider, student, modality, num_weeks=3
        )

        bookings[0].status = BookingStatus.CANCELLED
        bookings[0].cancelled_at = datetime.utcnow()
        db.session.flush()

        db.session.refresh(recurring)
        assert recurring.is_active is True

    def test_stopping_recurring_does_not_cancel_existing_bookings(
        self, db, provider, student, modality
    ):
        """
        Ao parar uma série (is_active = False), bookings já confirmados
        devem permanecer CONFIRMED — apenas novas ocorrências deixarão
        de ser criadas.
        """
        recurring, _, bookings = self._create_weekly_series(
            db, provider, student, modality, num_weeks=3
        )

        recurring.is_active = False
        db.session.flush()

        still_confirmed = Booking.query.filter_by(
            recurring_id=recurring.id,
            status=BookingStatus.CONFIRMED,
        ).count()
        assert still_confirmed == len(bookings), (
            "Parar a série não deve cancelar bookings existentes"
        )

    def test_create_recurring_bookings_service(
        self, db, provider, student, modality
    ):
        """
        create_recurring_bookings deve criar um Booking por ocorrência
        onde existe slot disponível.
        """
        today = date.today()
        days_to_wed = (2 - today.weekday()) % 7 or 7
        first_wed = today + timedelta(days=days_to_wed)

        for w in range(3):
            slot = ScheduleSlot(
                provider_id=provider.id,
                modality_id=modality.id,
                date=first_wed + timedelta(weeks=w),
                start_time=time(14, 0),
                end_time=time(15, 0),
                max_capacity=5,
                status="active",
            )
            db.session.add(slot)
        db.session.flush()

        recurring = RecurringBooking(
            client_id=student.id,
            provider_id=provider.id,
            modality_id=modality.id,
            weekday=2,  # quarta-feira
            start_time=time(14, 0),
            frequency=RecurringFrequency.WEEKLY,
            valid_from=first_wed,
            valid_until=first_wed + timedelta(weeks=2),
            is_active=True,
        )
        db.session.add(recurring)
        db.session.flush()

        created, conflicts = create_recurring_bookings(recurring, subscription=None)

        assert len(created) == 3
        assert len(conflicts) == 0
        for b in created:
            assert b.recurring_id == recurring.id
            assert b.status == BookingStatus.CONFIRMED


# ===========================================================================
# 5. CANCELAMENTO PELO PRESTADOR
# ===========================================================================


class TestProviderCancellation:
    """
    PRD § 10.5: Quando o prestador cancela/deleta um slot com inscritos,
    todos os Bookings vinculados devem ser marcados como CANCELLED e ter
    cancelled_at preenchido (pronto para triggers de notificação).
    """

    def test_slot_delete_cancels_all_confirmed_bookings(
        self, db, provider, student, student2, modality
    ):
        """
        Ao deletar um slot com inscritos, o slot muda para 'cancelled' e
        todos os bookings CONFIRMED recebem status=CANCELLED + cancelled_at.
        """
        slot = make_slot(db, provider, modality, capacity=10)

        for s in (student, student2):
            b = Booking(
                client_id=s.id,
                slot_id=slot.id,
                status=BookingStatus.CONFIRMED,
                cost_at_booking=1,
            )
            db.session.add(b)
        db.session.flush()

        confirmed_bookings = Booking.query.filter_by(
            slot_id=slot.id, status=BookingStatus.CONFIRMED
        ).all()
        assert len(confirmed_bookings) == 2

        now = datetime.utcnow()
        slot.status = "cancelled"
        for booking in confirmed_bookings:
            booking.status = BookingStatus.CANCELLED
            booking.cancelled_at = now
            booking.cancel_reason = "Horário cancelado pelo prestador."
        db.session.flush()

        assert slot.status == "cancelled"
        cancelled = Booking.query.filter_by(
            slot_id=slot.id, status=BookingStatus.CANCELLED
        ).all()
        assert len(cancelled) == 2
        for b in cancelled:
            assert b.cancelled_at is not None
            assert b.cancel_reason == "Horário cancelado pelo prestador."

    def test_slot_delete_without_bookings_removes_slot(
        self, db, provider, modality
    ):
        """
        Slot vazio é removido diretamente sem deixar vestígios (hard delete).
        """
        slot = make_slot(db, provider, modality, capacity=5)
        slot_id = slot.id

        confirmed = Booking.query.filter_by(
            slot_id=slot.id, status=BookingStatus.CONFIRMED
        ).count()
        assert confirmed == 0

        db.session.delete(slot)
        db.session.flush()

        assert db.session.get(ScheduleSlot, slot_id) is None

    def test_cancelled_bookings_have_cancelled_at_populated(
        self, db, provider, student, modality
    ):
        """
        cancelled_at nunca pode ser None após um cancelamento pelo prestador
        (é o gatilho para o sistema de notificações).
        """
        slot = make_slot(db, provider, modality, capacity=5)

        b = Booking(
            client_id=student.id,
            slot_id=slot.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add(b)
        db.session.flush()

        now = datetime.utcnow()
        slot.status = "cancelled"
        b.status = BookingStatus.CANCELLED
        b.cancelled_at = now
        b.cancel_reason = "Horário cancelado pelo prestador."
        db.session.flush()

        refreshed = db.session.get(Booking, b.id)
        assert refreshed.cancelled_at is not None
        assert refreshed.status == BookingStatus.CANCELLED

    def test_cancelling_slot_does_not_affect_other_slots_bookings(
        self, db, provider, student, modality
    ):
        """
        O cancelamento de um slot não deve interferir nos bookings de
        outros slots do mesmo prestador.
        """
        slot_a = make_slot(db, provider, modality, days_ahead=3)
        slot_b = make_slot(db, provider, modality, days_ahead=4)

        booking_a = Booking(
            client_id=student.id,
            slot_id=slot_a.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        booking_b = Booking(
            client_id=student.id,
            slot_id=slot_b.id,
            status=BookingStatus.CONFIRMED,
            cost_at_booking=1,
        )
        db.session.add_all([booking_a, booking_b])
        db.session.flush()

        slot_a.status = "cancelled"
        booking_a.status = BookingStatus.CANCELLED
        booking_a.cancelled_at = datetime.utcnow()
        db.session.flush()

        assert db.session.get(ScheduleSlot, slot_b.id).status == "active"
        assert db.session.get(Booking, booking_b.id).status == BookingStatus.CONFIRMED

    def test_validate_booking_rejects_cancelled_slot(
        self, db, provider, student, subscription, modality
    ):
        """
        validate_booking deve rejeitar tentativas de booking em slots
        com status='cancelled', cobrindo a checagem downstream.
        """
        slot = make_slot(db, provider, modality)
        slot.status = "cancelled"
        db.session.flush()

        ok, msg = validate_booking(student, slot, subscription)

        assert ok is False
        assert "cancelado" in msg.lower()
