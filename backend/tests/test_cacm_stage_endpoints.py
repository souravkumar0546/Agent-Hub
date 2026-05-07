"""Smoke tests for the wizard's `/api/cacm/runs/{id}/stage/*` endpoints.

Mirrors the pattern from `test_cacm_routes.py` (StaticPool SQLite +
dependency_overrides) so the tests don't need the real DB or auth flow.
We plant a `CacmRun` row and walk each stage endpoint to verify shape +
key invariants.
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
from app.models.cacm import CacmRun


@pytest.fixture
def setup():
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
        user = User(
            email="a@b.c", name="A", password_hash="x",
            is_super_admin=False, is_active=True,
        )
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


def _plant_procurement_run(LocalSession, org_id, user_id) -> int:
    with LocalSession() as s:
        run = CacmRun(
            org_id=org_id, user_id=user_id,
            kpi_type="po_after_invoice", process="Procurement",
            status="succeeded",
            total_records=260, total_exceptions=32, exception_pct=12.3,
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        return run.id


def test_stage_extraction_returns_planned_tables_and_samples(setup):
    client, LocalSession, org_id, user_id = setup
    run_id = _plant_procurement_run(LocalSession, org_id, user_id)
    r = client.get(f"/api/cacm/runs/{run_id}/stage/extraction")
    assert r.status_code == 200
    body = r.json()
    assert body["source_system"] == "SAP ECC (sample)"
    assert body["planned_tables"] == ["EKBE", "EKKO", "EKPO", "EBAN", "T5VS5"]
    names = {t["name"] for t in body["tables"]}
    # Procurement sample data ships ekko / rbkp / lfa1.
    assert {"ekko", "rbkp", "lfa1"}.issubset(names)
    # Sample rows are dicts and capped at 10.
    for t in body["tables"]:
        assert len(t["sample_rows"]) <= 10
        if t["sample_rows"]:
            assert isinstance(t["sample_rows"][0], dict)
        assert t["download_url"].endswith(f"/{t['name']}.csv")


def test_stage_transformation_lists_rules_and_derived_tables(setup):
    client, LocalSession, org_id, user_id = setup
    run_id = _plant_procurement_run(LocalSession, org_id, user_id)
    r = client.get(f"/api/cacm/runs/{run_id}/stage/transformation")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["rules_applied"], list) and body["rules_applied"]
    assert body["rows_in"] > 0
    derived_names = {d["name"] for d in body["derived_tables"]}
    assert "po_invoice_joined" in derived_names


def test_stage_loading_reports_ccm_targets(setup):
    client, LocalSession, org_id, user_id = setup
    run_id = _plant_procurement_run(LocalSession, org_id, user_id)
    r = client.get(f"/api/cacm/runs/{run_id}/stage/loading")
    assert r.status_code == 200
    body = r.json()
    names = {t["name"] for t in body["target_tables"]}
    # The procurement load targets explicitly include these CCM mart tables.
    assert {
        "ccm_po_header", "ccm_po_line_items", "ccm_vendor_master",
        "ccm_invoice_header", "ccm_invoice_line_items", "ccm_rule_execution_log",
    }.issubset(names)
    for t in body["target_tables"]:
        assert t["status"] == "loaded"


def test_stage_rule_engine_surfaces_kpi_conditions(setup):
    client, LocalSession, org_id, user_id = setup
    run_id = _plant_procurement_run(LocalSession, org_id, user_id)
    r = client.get(f"/api/cacm/runs/{run_id}/stage/rule-engine")
    assert r.status_code == 200
    body = r.json()
    assert body["kpi_type"] == "po_after_invoice"
    assert body["pattern"] == "date_compare"
    assert isinstance(body["conditions"], list) and len(body["conditions"]) >= 4
    assert body["exceptions_generated"] == 32
    assert body["total_evaluated"] > 0


def test_stage_extraction_csv_download_returns_csv(setup):
    client, LocalSession, org_id, user_id = setup
    run_id = _plant_procurement_run(LocalSession, org_id, user_id)
    r = client.get(f"/api/cacm/runs/{run_id}/stage/extraction/download/ekko.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    # CSV header row should include enriched columns.
    head = r.content.split(b"\n", 1)[0].decode()
    for col in ("po_no", "company_code", "po_amount", "po_approval_status"):
        assert col in head


def test_stage_endpoint_404s_for_other_org(setup):
    client, LocalSession, org_id, _ = setup
    with LocalSession() as s:
        other = Organization(name="Y", slug="y", is_active=True)
        s.add(other)
        s.commit()
        s.refresh(other)
        run = CacmRun(
            org_id=other.id, kpi_type="po_after_invoice",
            process="Procurement", status="succeeded",
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
    for tail in ("extraction", "transformation", "loading", "rule-engine"):
        r = client.get(f"/api/cacm/runs/{run_id}/stage/{tail}")
        assert r.status_code == 404
