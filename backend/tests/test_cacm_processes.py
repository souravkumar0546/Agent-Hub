"""Sanity tests for the CACM process catalog + /processes endpoint."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.cacm.kpi_catalog import KPI_CATALOG
from app.agents.cacm.process_catalog import PROCESS_CATALOG
from app.api.deps import OrgContext, get_db, require_org
from app.core.database import Base
from app.main import app
from app.models import Organization, User


def test_eight_processes_in_catalog():
    assert len(PROCESS_CATALOG) == 8


def test_kris_reference_real_kpi_types():
    known_types = {k.type for k in KPI_CATALOG}
    for proc in PROCESS_CATALOG:
        for kri in proc.kris:
            assert kri.kpi_type is not None, (
                f"KRI {kri.name!r} in {proc.key!r} missing kpi_type"
            )
            assert kri.kpi_type in known_types, (
                f"KRI {kri.name!r} references unknown kpi_type {kri.kpi_type!r}"
            )


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
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_processes_endpoint_returns_eight(client):
    r = client.get("/api/cacm/processes")
    assert r.status_code == 200
    body = r.json()
    assert "processes" in body
    assert len(body["processes"]) == 8
    keys = {p["key"] for p in body["processes"]}
    assert "procurement_to_payment" in keys
    assert "inventory_management" in keys
    # spot-check shape
    p2p = next(p for p in body["processes"] if p["key"] == "procurement_to_payment")
    assert any(k["kpi_type"] == "po_after_invoice" for k in p2p["kris"])


def test_process_detail_endpoint(client):
    r = client.get("/api/cacm/processes/inventory_management")
    assert r.status_code == 200
    body = r.json()
    assert body["key"] == "inventory_management"
    assert any(k["kpi_type"] == "repeated_material_adjustments" for k in body["kris"])


def test_process_detail_404_for_unknown_key(client):
    r = client.get("/api/cacm/processes/nope_does_not_exist")
    assert r.status_code == 404
