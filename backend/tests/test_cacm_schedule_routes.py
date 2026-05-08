"""HTTP-level tests for /api/cacm/schedules CRUD."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import OrgContext, get_db, require_org
from app.core.database import Base
from app.main import app
from app.models import Organization, User


@pytest.fixture
def client():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    LocalSession = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    with LocalSession() as s:
        org_a = Organization(name="A", slug="a", is_active=True)
        org_b = Organization(name="B", slug="b", is_active=True)
        user = User(email="a@b.c", name="A", password_hash="x",
                    is_super_admin=False, is_active=True)
        s.add_all([org_a, org_b, user])
        s.commit()
        s.refresh(org_a)
        s.refresh(org_b)
        s.refresh(user)
        ids = (org_a.id, org_b.id, user.id)

    def _override_db():
        s = LocalSession()
        try:
            yield s
        finally:
            s.close()

    org_a_id, _org_b_id, user_id = ids
    active = {"org_id": org_a_id}

    def _override_require_org():
        with LocalSession() as ses:
            u = ses.get(User, user_id)
            return OrgContext(user=u, membership=None, org_id=active["org_id"])

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_org] = _override_require_org
    try:
        yield TestClient(app), ids, active
    finally:
        app.dependency_overrides.clear()


def test_post_schedule_creates_and_resolves_kpi_type(client):
    c, _ids, _active = client
    r = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kpi_type"] == "po_after_invoice"
    assert body["frequency"] == "daily"
    assert body["time_of_day"] == "09:00"
    assert body["last_run_id"] is None
    assert body["next_run_at"]


def test_post_schedule_rejects_unknown_kri(client):
    c, _, _ = client
    r = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "made up kri name",
        "frequency": "daily",
        "time_of_day": "09:00",
    })
    assert r.status_code == 400


def test_post_schedule_upserts_on_same_kri(client):
    c, _, _ = client
    body = {
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }
    r1 = c.post("/api/cacm/schedules", json=body)
    assert r1.status_code == 201
    body["frequency"] = "weekly"
    r2 = c.post("/api/cacm/schedules", json=body)
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["frequency"] == "weekly"


def test_get_schedules_filters_by_process(client):
    c, _, _ = client
    c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    })
    c.post("/api/cacm/schedules", json={
        "process_key": "inventory_management",
        "kri_name": "Repeated adjustments for same materials",
        "frequency": "weekly",
        "time_of_day": "10:00",
    })
    all_ = c.get("/api/cacm/schedules").json()["schedules"]
    assert len(all_) == 2
    only_p2p = c.get("/api/cacm/schedules", params={
        "process_key": "procurement_to_payment",
    }).json()["schedules"]
    assert len(only_p2p) == 1
    assert only_p2p[0]["process_key"] == "procurement_to_payment"


def test_put_schedule_updates_and_recomputes_next(client):
    c, _, _ = client
    created = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }).json()
    r = c.put(f"/api/cacm/schedules/{created['id']}", json={
        "frequency": "weekly",
        "time_of_day": "10:30",
    })
    assert r.status_code == 200
    out = r.json()
    assert out["frequency"] == "weekly"
    assert out["time_of_day"] == "10:30"
    assert out["next_run_at"] != created["next_run_at"]


def test_delete_schedule(client):
    c, _, _ = client
    created = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }).json()
    r = c.delete(f"/api/cacm/schedules/{created['id']}")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert c.get("/api/cacm/schedules").json()["schedules"] == []


def test_get_404_for_other_org_schedule(client):
    c, ids, active = client
    org_a_id, org_b_id, _user_id = ids
    created = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }).json()
    active["org_id"] = org_b_id
    try:
        r = c.put(f"/api/cacm/schedules/{created['id']}", json={
            "frequency": "weekly", "time_of_day": "09:00",
        })
        assert r.status_code == 404
        r = c.delete(f"/api/cacm/schedules/{created['id']}")
        assert r.status_code == 404
    finally:
        active["org_id"] = org_a_id
