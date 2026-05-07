"""Smoke tests for the /api/cacm/* routes.

Uses an in-memory SQLite + a `dependency_overrides` swap so the FastAPI
test client doesn't need the real Neon DB or auth flow. The pipeline
behaviour itself is covered by `test_cacm_pipeline.py`; here we just
verify the wiring + happy-path response shapes.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import OrgContext, get_db, require_org
from app.core.database import Base
from app.main import app
from app.models import Organization, User
from app.models.cacm import CacmException, CacmRun, CacmRunEvent


@pytest.fixture
def setup():
    # SQLite `:memory:` is per-connection; use StaticPool so the engine
    # hands the same connection to every Session — otherwise the schema
    # we create up-front isn't visible to the request-scoped Sessions
    # that get_db hands out.
    from sqlalchemy.pool import StaticPool

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
        org_id, user_id = org.id, user.id

    def _override_db():
        s = LocalSession()
        try:
            yield s
        finally:
            s.close()

    def _override_require_org():
        # The handlers only read .org_id and .user.id from the context.
        with LocalSession() as ses:
            u = ses.get(User, user_id)
            return OrgContext(user=u, membership=None, org_id=org_id)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_org] = _override_require_org

    client = TestClient(app)
    try:
        yield client, LocalSession, org_id, user_id
    finally:
        app.dependency_overrides.clear()


def test_library_returns_processes_and_kpis(setup):
    client, *_ = setup
    r = client.get("/api/cacm/library")
    assert r.status_code == 200
    body = r.json()
    procs = body["processes"]
    proc_names = {p["name"] for p in procs}
    assert {"Procurement", "Inventory"}.issubset(proc_names)
    proc = next(p for p in procs if p["name"] == "Procurement")
    assert any(k["type"] == "po_after_invoice" for k in proc["kpis"])


def test_unknown_kpi_type_returns_400(setup):
    client, *_ = setup
    r = client.post("/api/cacm/runs", json={"kpi_type": "no_such_kpi"})
    assert r.status_code == 400


def test_run_summary_404_for_other_org(setup):
    """Run from another org should not be visible."""
    client, LocalSession, org_id, _ = setup
    with LocalSession() as s:
        # Make a different org and a run inside it.
        other = Organization(name="Y", slug="y", is_active=True)
        s.add(other)
        s.commit()
        s.refresh(other)
        run = CacmRun(org_id=other.id, kpi_type="po_after_invoice",
                      process="Procurement", status="running")
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
    r = client.get(f"/api/cacm/runs/{run_id}")
    assert r.status_code == 404


def test_runs_list_events_exceptions_and_dashboard_against_planted_run(setup):
    """End-to-end on the route surface — plant a run + events + exceptions
    directly in the DB, then walk every read endpoint."""
    client, LocalSession, org_id, _ = setup
    with LocalSession() as s:
        run = CacmRun(
            org_id=org_id, kpi_type="po_after_invoice",
            process="Procurement", status="succeeded",
            total_records=100, total_exceptions=2, exception_pct=2.0,
            summary_json={"risk_counts": {"High": 1, "Low": 1}},
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
        s.add_all([
            CacmRunEvent(run_id=run_id, seq=1, stage="extract", message="m1"),
            CacmRunEvent(run_id=run_id, seq=2, stage="rules", message="m2"),
        ])
        s.add_all([
            CacmException(
                run_id=run_id, exception_no="EX-0001", risk="High",
                payload_json={
                    "reason": "boom",
                    "value": 1.0,
                    "fields": {"po_no": "P1", "vendor_code": "V1",
                               "company_code": "1000", "po_created": "2026-04-01"},
                    "recommended_action": "look at it",
                },
            ),
            CacmException(
                run_id=run_id, exception_no="EX-0002", risk="Low",
                payload_json={"reason": "small", "value": 0.5, "fields": {}},
            ),
        ])
        s.commit()

    # GET /runs
    r = client.get("/api/cacm/runs")
    assert r.status_code == 200
    rows = r.json()
    assert any(row["id"] == run_id for row in rows)

    # GET /runs/{id}
    r = client.get(f"/api/cacm/runs/{run_id}")
    assert r.status_code == 200
    assert r.json()["status"] == "succeeded"

    # GET /runs/{id}/events?since=0  → 2 events
    r = client.get(f"/api/cacm/runs/{run_id}/events?since=0")
    body = r.json()
    assert body["status"] == "succeeded"
    assert len(body["events"]) == 2

    # since cursor filter
    r = client.get(f"/api/cacm/runs/{run_id}/events?since=1")
    assert len(r.json()["events"]) == 1
    assert r.json()["events"][0]["seq"] == 2

    # GET /runs/{id}/exceptions
    r = client.get(f"/api/cacm/runs/{run_id}/exceptions")
    body = r.json()
    assert body["total"] == 2

    # risk filter
    r = client.get(f"/api/cacm/runs/{run_id}/exceptions?risk=High")
    assert r.json()["total"] == 1

    # CSV download
    r = client.get(f"/api/cacm/runs/{run_id}/exceptions.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert b"exception_no" in r.content
    assert b"EX-0001" in r.content

    # XLSX download
    r = client.get(f"/api/cacm/runs/{run_id}/exceptions.xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    assert r.content[:2] == b"PK"  # xlsx is a zip

    # Dashboard
    r = client.get(f"/api/cacm/runs/{run_id}/dashboard")
    body = r.json()
    assert body["totals"]["exceptions"] == 2
    assert body["by_risk"] == {"High": 1, "Low": 1}
    assert body["by_company"] == {"1000": 1}
    assert body["by_vendor"] == {"V1": 1}


def test_cacm_routes_registered_in_main_app():
    """Defends against the route file existing but never being included."""
    paths = sorted({getattr(r, "path", "") for r in app.routes if "/api/cacm" in getattr(r, "path", "")})
    expected = [
        "/api/cacm/library",
        "/api/cacm/runs",
        "/api/cacm/runs/{run_id}",
        "/api/cacm/runs/{run_id}/dashboard",
        "/api/cacm/runs/{run_id}/events",
        "/api/cacm/runs/{run_id}/exceptions",
        "/api/cacm/runs/{run_id}/exceptions.csv",
        "/api/cacm/runs/{run_id}/exceptions.xlsx",
    ]
    for path in expected:
        assert path in paths, f"missing {path} in {paths}"
