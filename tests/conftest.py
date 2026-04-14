# tests/conftest.py
"""
Fixtures compartilhadas para toda a suíte de testes.

Usa SQLite em memória (:memory:) para isolamento total entre testes.
"""

from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from app import create_app, db as _db
from app.models.booking import Booking, BookingStatus
from app.models.modality import Modality
from app.models.schedule_slot import ScheduleSlot
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.user import User


# ---------------------------------------------------------------------------
# App / DB
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app():
    """Flask application configured for testing with in-memory SQLite."""
    _app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_ENGINE_OPTIONS": {"connect_args": {"check_same_thread": False}},
            "WTF_CSRF_ENABLED": False,
            "LOGIN_DISABLED": False,
            "SECRET_KEY": "test-secret",
        }
    )
    with _app.app_context():
        _db.create_all()
        yield _app
        _db.drop_all()


@pytest.fixture(scope="function")
def db(app):
    """
    Yields the SQLAlchemy db object.
    Each test runs inside a savepoint that is rolled back afterwards,
    ensuring full isolation without recreating the schema.
    """
    connection = _db.engine.connect()
    transaction = connection.begin()

    # Bind a scoped session to this connection
    _db.session.bind = connection  # type: ignore[attr-defined]

    yield _db

    _db.session.remove()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(app, db):
    """Flask test client, authenticated as the student fixture by default."""
    return app.test_client()


# ---------------------------------------------------------------------------
# Domain fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="function")
def provider(db):
    """Instructor/provider user."""
    u = User(
        name="Provider Test",
        email="provider@test.com",
        phone="11999990000",
        role="instructor",
        schedule_policy_json={
            "min_notice_hours": 2,
            "cancel_deadline_hours": 4,
            "max_future_days": 60,
        },
    )
    u.set_password("senha123")
    db.session.add(u)
    db.session.flush()
    return u


@pytest.fixture(scope="function")
def student(db):
    """Regular student user."""
    u = User(
        name="Student Test",
        email="student@test.com",
        phone="11888880000",
        role="student",
    )
    u.set_password("senha123")
    db.session.add(u)
    db.session.flush()
    return u


@pytest.fixture(scope="function")
def student2(db):
    """Second student for concurrency tests."""
    u = User(
        name="Student Two",
        email="student2@test.com",
        phone="11777770000",
        role="student",
    )
    u.set_password("senha123")
    db.session.add(u)
    db.session.flush()
    return u


@pytest.fixture(scope="function")
def modality(db):
    m = Modality(name="Musculação", credits_cost=1, slot_duration_min=60)
    db.session.add(m)
    db.session.flush()
    return m


@pytest.fixture(scope="function")
def subscription(db, student):
    """Active subscription with 5 credits for the student."""
    s = Subscription(
        user_id=student.id,
        name="Plano Mensal",
        credits_total=5,
        credits_used=0,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        status=SubscriptionStatus.ACTIVE,
    )
    db.session.add(s)
    db.session.flush()
    return s


@pytest.fixture(scope="function")
def subscription2(db, student2):
    """Active subscription for the second student."""
    s = Subscription(
        user_id=student2.id,
        name="Plano Mensal",
        credits_total=5,
        credits_used=0,
        start_date=date.today(),
        end_date=date.today() + timedelta(days=30),
        status=SubscriptionStatus.ACTIVE,
    )
    db.session.add(s)
    db.session.flush()
    return s


def make_slot(db, provider, modality=None, *, days_ahead=3, capacity=1, **kwargs):
    """Factory helper: creates and flushes a ScheduleSlot."""
    target = date.today() + timedelta(days=days_ahead)
    slot = ScheduleSlot(
        provider_id=provider.id,
        modality_id=modality.id if modality else None,
        date=target,
        start_time=time(10, 0),
        end_time=time(11, 0),
        max_capacity=capacity,
        status="active",
        **kwargs,
    )
    db.session.add(slot)
    db.session.flush()
    return slot
