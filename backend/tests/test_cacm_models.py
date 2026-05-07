"""Smoke test that the CACM ORM models are wired and round-trip cleanly."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import (
    Organization, User,
    CacmRun, CacmRunEvent, CacmException,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def test_models_round_trip(db):
    org = Organization(name="X", slug="x", is_active=True)
    user = User(email="a@b.c", name="A", password_hash="x", is_super_admin=False, is_active=True)
    db.add_all([org, user])
    db.flush()

    run = CacmRun(
        org_id=org.id, user_id=user.id,
        kpi_type="po_after_invoice", process="Procurement",
        status="running",
    )
    db.add(run)
    db.flush()

    db.add(CacmRunEvent(run_id=run.id, seq=1, stage="extract", message="hi"))
    db.add(CacmException(run_id=run.id, exception_no="EX-0001", risk="High", payload_json={"a": 1}))
    db.commit()

    assert db.query(CacmRun).count() == 1
    assert db.query(CacmRunEvent).count() == 1
    assert db.query(CacmException).count() == 1
