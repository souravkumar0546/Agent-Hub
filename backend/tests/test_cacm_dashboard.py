"""Sanity tests for the rebuilt /api/cacm/runs/{id}/dashboard endpoint.

Plant a procurement-shaped exception set directly into the DB, then walk
the new dashboard response shape. Two cases:
  1. Default (no filters) — assert all top-level keys + sane totals.
  2. Filtered (?risk_levels=High) — assert totals.total_exceptions only
     counts High-risk rows.
"""
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
from app.models.cacm import CacmException, CacmRun


# A small, hand-engineered set covering all 3 risk bands and 2 companies/locations
# so monthly_trend, company_breakdown, aging_buckets etc. all have ≥1 row.
_PLANTED = [
    # (exception_no, risk, diff_days, company, location, po_user, inv_amt, po_amt, po_created)
    ("EX-0001", "Low", 2, "1000", "Mumbai - MUM1", "Rekha Nair", 12500, 12500, "2025-04-15"),
    ("EX-0002", "Low", 3, "1000", "Mumbai - MUM1", "Meena Iyer", 75000, 75000, "2025-05-10"),
    ("EX-0003", "Medium", 7, "2000", "Delhi - DEL1", "Amit Singh", 312500, 312500, "2025-06-20"),
    ("EX-0004", "Medium", 12, "2000", "Delhi - DEL1", "Rekha Nair", 234100, 234100, "2025-07-05"),
    ("EX-0005", "High", 18, "1000", "Mumbai - MUM1", "Meena Iyer", 612000, 612000, "2025-08-15"),
    ("EX-0006", "High", 28, "2000", "Delhi - DEL1", "Amit Singh", 825000, 825000, "2025-09-12"),
]


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

    # Plant a run + 6 exceptions.
    with LocalSession() as s:
        run = CacmRun(
            org_id=org_id, kpi_type="po_after_invoice",
            process="Procurement", status="succeeded",
            total_records=290, total_exceptions=len(_PLANTED), exception_pct=2.0,
            summary_json={"risk_counts": {"High": 2, "Medium": 2, "Low": 2}},
        )
        s.add(run)
        s.commit()
        s.refresh(run)
        run_id = run.id
        for no, risk, diff, cc, loc, user, inv_amt, po_amt, po_created in _PLANTED:
            s.add(CacmException(
                run_id=run_id, exception_no=no, risk=risk,
                payload_json={
                    "reason": "x",
                    "value": float(diff),
                    "fields": {
                        "po_no": no.replace("EX-", "PO"),
                        "inv_no": no.replace("EX-", "INV"),
                        "vendor_code": "V001",
                        "company_code": cc,
                        "location": loc,
                        "po_created_by": user,
                        "po_created": po_created,
                        "invoice_posted": "2025-04-01",
                        "po_amount": po_amt,
                        "invoice_amount": inv_amt,
                        "diff_days": diff,
                    },
                },
            ))
        s.commit()

    client = TestClient(app)
    try:
        yield client, run_id
    finally:
        app.dependency_overrides.clear()


def test_dashboard_full_shape(setup):
    client, run_id = setup
    r = client.get(f"/api/cacm/runs/{run_id}/dashboard")
    assert r.status_code == 200
    body = r.json()

    # All top-level keys present.
    expected_keys = {
        "totals", "filter_options", "monthly_trend", "company_breakdown",
        "aging_buckets", "po_creators", "financial_exposure", "location_breakdown",
    }
    assert expected_keys.issubset(body.keys())

    # Totals
    t = body["totals"]
    assert t["total_exceptions"] == 6
    assert t["high_risk_count"] == 2
    assert t["high_risk_pct"] == pytest.approx(33.3, abs=0.2)
    assert t["max_delay_days"] == 28
    assert t["max_delay_location"] == "Delhi - DEL1"
    # avg = (2+3+7+12+18+28)/6 = 11.67
    assert t["avg_delay_days"] == pytest.approx(11.7, abs=0.1)

    # Filter options
    fo = body["filter_options"]
    assert set(fo["companies"]) == {"1000", "2000"}
    assert set(fo["locations"]) == {"Mumbai - MUM1", "Delhi - DEL1"}
    assert fo["risk_levels"] == ["High", "Medium", "Low"]
    assert fo["aging_buckets"] == ["0-3 Days", "4-14 Days", "15+ Days"]
    assert {"Rekha Nair", "Meena Iyer", "Amit Singh"}.issubset(set(fo["po_creators"]))

    # Aging buckets — always 3 items
    ages = {b["label"]: b for b in body["aging_buckets"]}
    assert ages["0-3 Days"]["count"] == 2
    assert ages["4-14 Days"]["count"] == 2
    assert ages["15+ Days"]["count"] == 2

    # Company breakdown
    by_cc = {c["company_code"]: c for c in body["company_breakdown"]}
    assert "1000" in by_cc and "2000" in by_cc
    assert by_cc["1000"]["count"] == 3
    assert by_cc["2000"]["count"] == 3

    # Monthly trend non-empty + sorted
    assert len(body["monthly_trend"]) == 6  # one row per month

    # Financial exposure has one row per exception
    assert len(body["financial_exposure"]) == 6

    # Location breakdown
    locs = {l["location"]: l for l in body["location_breakdown"]}
    assert locs["Mumbai - MUM1"]["count"] == 3
    assert locs["Delhi - DEL1"]["count"] == 3


def test_dashboard_filter_high_risk(setup):
    client, run_id = setup
    r = client.get(
        f"/api/cacm/runs/{run_id}/dashboard",
        params={"risk_levels": "High"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["totals"]["total_exceptions"] == 2
    assert body["totals"]["high_risk_count"] == 2
    # Filter options NEVER shrink — should still list all 2 companies.
    assert set(body["filter_options"]["companies"]) == {"1000", "2000"}
    assert len(body["financial_exposure"]) == 2
