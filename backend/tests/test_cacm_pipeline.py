"""End-to-end pipeline test: run a known KPI on its sample data, assert
events + exceptions.

Uses an in-memory SQLite DB so the test doesn't touch the real Neon DB
and runs in a few hundred ms (zero-pause sleep_fn).
"""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agents.cacm.service import run_pipeline
from app.core.database import Base
from app.models import Organization, User
from app.models.cacm import CacmException, CacmRun, CacmRunEvent


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        org = Organization(name="X", slug="x", is_active=True)
        user = User(email="a@b.c", name="A", password_hash="x",
                    is_super_admin=False, is_active=True)
        s.add_all([org, user])
        s.commit()
        s.refresh(org)
        s.refresh(user)
        yield s, org, user


def test_po_after_invoice_pipeline_produces_events_and_exceptions(db):
    s, org, user = db
    run = CacmRun(
        org_id=org.id, user_id=user.id, kpi_type="po_after_invoice",
        process="Procurement", status="running",
    )
    s.add(run)
    s.commit()
    s.refresh(run)

    # Skip the theatrical pauses — test should run sub-second.
    asyncio.run(run_pipeline(s, run.id, sleep_fn=lambda _: asyncio.sleep(0)))

    s.refresh(run)
    assert run.status == "succeeded"
    assert run.completed_at is not None
    assert run.total_records is not None and run.total_records > 0
    # Engineered procurement.json fires ~32 retroactive POs in the date_compare check.
    assert run.total_exceptions is not None
    assert 25 <= run.total_exceptions <= 35, f"got {run.total_exceptions}"

    # All six stages fire in order.
    events = (
        s.query(CacmRunEvent)
        .filter_by(run_id=run.id)
        .order_by(CacmRunEvent.seq)
        .all()
    )
    stages = [e.stage for e in events]
    distinct = sorted(set(stages))
    assert sorted(["extract", "transform", "load", "rules", "exceptions", "dashboard"]) == distinct
    assert (
        stages.index("extract") < stages.index("transform")
        < stages.index("load") < stages.index("rules")
        < stages.index("exceptions") < stages.index("dashboard")
    )

    # Exceptions are numbered EX-0001, EX-0002, ...
    excs = (
        s.query(CacmException)
        .filter_by(run_id=run.id)
        .order_by(CacmException.id)
        .all()
    )
    assert len(excs) == run.total_exceptions
    assert excs[0].exception_no == "EX-0001"
    assert excs[1].exception_no == "EX-0002"
    # Recommended action got attached for the demo flow.
    assert "recommended_action" in excs[0].payload_json
