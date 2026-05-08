"""Scheduler tick logic — does it pick up due schedules and advance them?"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import CacmRun, CacmSchedule, Organization, User


@pytest.fixture
def session_factory():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)


@pytest.fixture
def seeded(session_factory, monkeypatch):
    s = session_factory()
    org = Organization(name="X", slug="x", is_active=True)
    user = User(email="a@b.c", name="A", password_hash="x",
                is_super_admin=False, is_active=True)
    s.add_all([org, user])
    s.commit()
    s.refresh(org)
    s.refresh(user)
    org_id = org.id
    user_id = user.id
    s.close()

    fired = []

    async def _fake_run_in_background(run_id):
        fired.append(run_id)

    # Stub before importing scheduler so the module-level import binding
    # picks up the fake.
    import app.api.routes.cacm as cacm_routes
    monkeypatch.setattr(cacm_routes, "_run_in_background", _fake_run_in_background)
    import app.agents.cacm.scheduler as scheduler_mod
    monkeypatch.setattr(scheduler_mod, "_run_in_background", _fake_run_in_background)

    return session_factory, org_id, user_id, fired


def _due_row(org_id, user_id, **overrides):
    base = dict(
        org_id=org_id,
        user_id=user_id,
        process_key="procurement_to_payment",
        kri_name="PO issued after invoice date (retroactive approvals)",
        kpi_type="po_after_invoice",
        frequency="daily",
        time_of_day="09:00",
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        is_active=True,
    )
    base.update(overrides)
    return CacmSchedule(**base)


def test_tick_fires_due_schedule_and_advances_next_run(seeded):
    from app.agents.cacm.scheduler import scheduler_tick
    factory, org_id, user_id, fired = seeded
    s = factory()
    s.add(_due_row(org_id, user_id))
    s.commit()
    s.close()

    scheduler_tick(factory)

    s = factory()
    sched = s.query(CacmSchedule).one()
    runs = s.query(CacmRun).all()
    assert len(runs) == 1
    assert runs[0].kpi_type == "po_after_invoice"
    assert runs[0].status == "running"
    assert sched.last_run_id == runs[0].id
    assert sched.last_run_at is not None
    # SQLite drops tzinfo on read-back even with DateTime(timezone=True);
    # values are stored as UTC, so re-attach UTC for the comparison.
    next_at = sched.next_run_at
    if next_at.tzinfo is None:
        next_at = next_at.replace(tzinfo=timezone.utc)
    assert next_at > datetime.now(timezone.utc)
    assert fired == [runs[0].id]
    s.close()


def test_tick_skips_inactive_schedules(seeded):
    from app.agents.cacm.scheduler import scheduler_tick
    factory, org_id, user_id, fired = seeded
    s = factory()
    s.add(_due_row(org_id, user_id, is_active=False))
    s.commit()
    s.close()

    scheduler_tick(factory)

    s = factory()
    assert s.query(CacmRun).count() == 0
    assert fired == []
    s.close()


def test_tick_skips_future_schedules(seeded):
    from app.agents.cacm.scheduler import scheduler_tick
    factory, org_id, user_id, fired = seeded
    s = factory()
    s.add(_due_row(
        org_id, user_id,
        next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    s.commit()
    s.close()

    scheduler_tick(factory)

    s = factory()
    assert s.query(CacmRun).count() == 0
    assert fired == []
    s.close()
