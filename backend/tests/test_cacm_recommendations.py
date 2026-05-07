"""Every KPI in the catalog must have a recommendation."""
from __future__ import annotations

from app.agents.cacm.kpi_catalog import KPI_CATALOG
from app.agents.cacm.recommendations import recommendation_for


def test_every_kpi_has_a_recommendation():
    for k in KPI_CATALOG:
        rec = recommendation_for(k.type)
        assert rec, f"missing recommendation for {k.type}"
        assert isinstance(rec, str)


def test_unknown_kpi_falls_back_to_default():
    rec = recommendation_for("nonexistent_kpi_type_xyz")
    assert rec  # default kicks in
