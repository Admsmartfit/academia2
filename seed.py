"""
seed.py — Popula o banco de dados com dados iniciais para testes.

Uso:
    python seed.py

Cria:
    - 1 usuário prestador  (instructor) → login: professor@academia.com / 123456
    - 1 usuário aluno      (student)    → login: aluno@academia.com    / 123456
    - 2 modalidades        (Musculação, Personal Training)
    - 1 template de disponibilidade (seg-sex, 07:00–09:00, 60 min, 10 vagas)
    - Slots gerados automaticamente para os próximos 30 dias
    - 1 assinatura ativa para o aluno (10 créditos)
"""

from datetime import date, time, timedelta

from app import create_app, db
from app.models.booking import Booking, BookingStatus
from app.models.modality import Modality
from app.models.schedule_slot import ScheduleSlot
from app.models.schedule_template import ScheduleTemplate
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User
from app.services.scheduling import generate_slots_from_template

app = create_app()

with app.app_context():
    # ── Limpar tudo ──────────────────────────────────────────────────────
    print("Limpando banco de dados...")
    Booking.query.delete()
    Subscription.query.delete()
    ScheduleSlot.query.delete()
    ScheduleTemplate.query.delete()
    Modality.query.delete()
    User.query.delete()
    db.session.commit()

    # ── Modalidades ───────────────────────────────────────────────────────
    print("Criando modalidades...")
    musculacao = Modality(
        name="Musculação",
        description="Treino de força com pesos livres e máquinas",
        credits_cost=1,
        slot_duration_min=60,
        color="#FF6B35",
        icon="fa-dumbbell",
        is_active=True,
    )
    personal = Modality(
        name="Personal Training",
        description="Treino personalizado 1:1",
        credits_cost=3,
        slot_duration_min=60,
        color="#004E89",
        icon="fa-user-shield",
        is_active=True,
    )
    db.session.add_all([musculacao, personal])
    db.session.flush()

    # ── Usuários ─────────────────────────────────────────────────────────
    print("Criando usuários...")
    professor = User(
        name="Prof. Carlos Silva",
        email="professor@academia.com",
        phone="11999990001",
        role="instructor",
        is_active=True,
        schedule_policy_json={
            "min_notice_hours": 2,
            "cancel_deadline_hours": 4,
            "max_future_days": 60,
        },
        bio="Personal trainer certificado com 10 anos de experiência.",
        specialties=["Musculação", "Hipertrofia", "Emagrecimento"],
    )
    professor.set_password("123456")

    aluno = User(
        name="Maria Oliveira",
        email="aluno@academia.com",
        phone="11888880001",
        role="student",
        is_active=True,
    )
    aluno.set_password("123456")

    db.session.add_all([professor, aluno])
    db.session.flush()

    # ── Assinatura do aluno ───────────────────────────────────────────────
    print("Criando assinatura...")
    hoje = date.today()
    sub = Subscription(
        user_id=aluno.id,
        name="Plano Mensal",
        credits_total=20,
        credits_used=0,
        start_date=hoje,
        end_date=hoje + timedelta(days=30),
        status=SubscriptionStatus.ACTIVE,
    )
    db.session.add(sub)
    db.session.flush()

    # ── Template de disponibilidade ───────────────────────────────────────
    print("Criando template de disponibilidade (seg-sex, 07:00–09:00)...")
    template = ScheduleTemplate(
        provider_id=professor.id,
        modality_id=musculacao.id,
        weekdays=[0, 1, 2, 3, 4],  # segunda a sexta
        start_time=time(7, 0),
        end_time=time(9, 0),
        slot_duration_min=60,
        max_capacity=10,
        valid_from=hoje,
        valid_until=hoje + timedelta(days=30),
        is_active=True,
    )
    db.session.add(template)
    db.session.flush()

    # ── Gerar slots ───────────────────────────────────────────────────────
    print("Gerando slots a partir do template...")
    created = generate_slots_from_template(template)
    db.session.commit()
    print(f"  {len(created)} slots criados.")

    # ── Resumo ────────────────────────────────────────────────────────────
    print("\n" + "="*50)
    print("Seed concluído com sucesso!\n")
    print("CREDENCIAIS DE ACESSO:")
    print(f"  Prestador: professor@academia.com  / 123456")
    print(f"  Aluno:     aluno@academia.com      / 123456")
    print(f"\nSlots criados: {len(created)}")
    print(f"Assinatura do aluno: {sub.credits_total} créditos (validade: {sub.end_date})")
    print("="*50)
