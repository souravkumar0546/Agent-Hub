"""Persistence tests for CacmSchedule — round-trip + unique constraint."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import CacmSchedule, Organization, User


@pytest.fixture
def session():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    LocalSession = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    with LocalSession() as s:
        org = Organization(name="X", slug="x", is_active=True)
        user = User(email="a@b.c", name="A", password_hash="x",
                    is_super_admin=False, is_active=True)
        s.add_all([org, user])
        s.commit()
        s.refresh(org)
        s.refresh(user)
        yield s, org, user


def _row(org, user, **overrides):
    base = dict(
        org_id=org.id,
        user_id=user.id,
        process_key="procurement_to_payment",
        kri_name="PO issued after invoice date (retroactive approvals)",
        kpi_type="po_after_invoice",
        frequency="daily",
        time_of_day="09:00",
        next_run_at=datetime(2026, 5, 9, 9, 0, tzinfo=timezone.utc),
        is_active=True,
    )
    base.update(overrides)
    return CacmSchedule(**base)


def test_round_trip(session):
    s, org, user = session
    s.add(_row(org, user))
    s.commit()
    out = s.query(CacmSchedule).one()
    assert out.process_key == "procurement_to_payment"
    assert out.frequency == "daily"
    assert out.time_of_day == "09:00"
    assert out.is_active is True
    assert out.last_run_id is None


def test_unique_per_org_process_kri(session):
    s, org, user = session
    s.add(_row(org, user))
    s.commit()
    s.add(_row(org, user, frequency="weekly"))
    with pytest.raises(IntegrityError):
        s.commit()
