"""End-to-end sanity for the Inventory KPI dashboard payload.

Runs the orchestrator pipeline once for the `repeated_material_adjustments`
KPI, then exercises the /dashboard endpoint:
  1. Default (no filters) — assert all top-level Inventory keys + sane totals.
  2. ?reversals=Yes — assert total_exceptions strictly drops (some
     non-reversal exceptions get filtered out).
"""
from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.cacm.service import run_pipeline
from app.api.deps import OrgContext, get_db, require_org
from app.core.database import Base
from app.main import app
from app.models import Organization, User
from app.models.cacm import CacmRun


@pytest.fixture
def setup():
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
        with LocalSession() as ses:
            u = ses.get(User, user_id)
            return OrgContext(user=u, membership=None, org_id=org_id)

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_org] = _override_require_org

    # Run the pipeline synchronously so exceptions land in the DB before
    # we hit the /dashboard endpoint.
    with LocalSession() as s:
        run = CacmRun(
            org_id=org_id, user_id=user_id,
            kpi_type="repeated_material_adjustments",
            process="Inventory", status="running",
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
        # Skip the theatrical sleeps so the pipeline returns quickly.
        asyncio.run(run_pipeline(s, run_id, sleep_fn=lambda _: asyncio.sleep(0)))

    client = TestClient(app)
    try:
        yield client, run_id
    finally:
        app.dependency_overrides.clear()


def test_inventory_dashboard_full_shape(setup):
    client, run_id = setup
    r = client.get(f"/api/cacm/runs/{run_id}/dashboard")
    assert r.status_code == 200, r.text
    body = r.json()

    # All top-level inventory keys present.
    expected = {
        "kpi_type", "process", "totals", "filter_options",
        "movement_type_distribution", "monthly_trend", "company_breakdown",
        "material_group_exposure", "location_analysis",
    }
    assert expected.issubset(body.keys())

    # KPI-type echo.
    assert body["kpi_type"] == "repeated_material_adjustments"
    assert body["process"] == "Inventory"

    # Totals sanity — pipeline produces ~120 exceptions on the regenerated
    # sample data; allow some headroom in case the dataset is rebalanced.
    t = body["totals"]
    assert t["total_exceptions"] >= 80
    assert t["high_risk_count"] > 0
    assert t["total_adj_value"] > 0
    assert t["avg_adj_count"] >= 4  # threshold > 3 in the kpi catalog
    assert t["unique_materials"] == t["total_exceptions"]

    # Filter options non-empty.
    fo = body["filter_options"]
    assert "companies" in fo and len(fo["companies"]) >= 1
    assert "locations" in fo and len(fo["locations"]) >= 1
    assert fo["risk_levels"] == ["High", "Medium", "Low"]
    assert "movement_types" in fo
    assert "material_groups" in fo
    assert fo["reversals"] == ["Yes", "No"]

    # Movement type distribution always returns 8 entries (the catalog).
    assert len(body["movement_type_distribution"]) == 8
    assert all("code" in row and "label" in row and "count" in row
               for row in body["movement_type_distribution"])

    # Monthly trend has at least one row.
    assert len(body["monthly_trend"]) >= 1
    assert all({"month", "exceptions", "total_value"}.issubset(row.keys())
               for row in body["monthly_trend"])

    # Company breakdown rows have High/Medium/Low fields.
    assert len(body["company_breakdown"]) >= 1
    for row in body["company_breakdown"]:
        assert {"company_code", "label", "high", "medium", "low"}.issubset(row.keys())

    # Material group exposure rows.
    assert len(body["material_group_exposure"]) >= 1
    for row in body["material_group_exposure"]:
        assert {"group", "value", "pct", "color"}.issubset(row.keys())

    # Location analysis rows.
    assert len(body["location_analysis"]) >= 1
    for row in body["location_analysis"]:
        assert {"location", "label", "count", "high_count", "color"}.issubset(row.keys())


def test_inventory_dashboard_reversals_filter(setup):
    client, run_id = setup
    r_all = client.get(f"/api/cacm/runs/{run_id}/dashboard")
    r_yes = client.get(
        f"/api/cacm/runs/{run_id}/dashboard",
        params={"reversals": "Yes"},
    )
    assert r_all.status_code == 200
    assert r_yes.status_code == 200
    total_all = r_all.json()["totals"]["total_exceptions"]
    total_yes = r_yes.json()["totals"]["total_exceptions"]
    # Yes-only must shrink (some exceptions are non-reversal). Strictly less.
    assert total_yes < total_all
    # Filter options never shrink.
    assert (
        r_all.json()["filter_options"]["companies"]
        == r_yes.json()["filter_options"]["companies"]
    )
