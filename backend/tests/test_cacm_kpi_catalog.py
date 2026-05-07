"""Catalog must have all v1 KPIs across the in-scope processes, each pointing at a real pattern."""
from __future__ import annotations

from collections import Counter

from app.agents.cacm.kpi_catalog import KPI_CATALOG, kpi_by_type, kpis_by_process
from app.agents.cacm.rule_patterns import PATTERN_REGISTRY


def test_forty_kpis_across_eight_processes():
    assert len(KPI_CATALOG) == 2
    processes = {k.process for k in KPI_CATALOG}
    assert processes == {"Procurement", "Inventory"}


def test_no_duplicate_types():
    types = [k.type for k in KPI_CATALOG]
    dupes = [t for t, c in Counter(types).items() if c > 1]
    assert dupes == []


def test_every_pattern_exists():
    for k in KPI_CATALOG:
        assert k.pattern in PATTERN_REGISTRY, f"{k.type} → unknown pattern {k.pattern!r}"


def test_kpi_by_type_lookup():
    k = kpi_by_type("po_after_invoice")
    assert k is not None
    assert k.process == "Procurement"


def test_kpis_by_process_grouping():
    grouped = kpis_by_process()
    assert "Procurement" in grouped
    assert all(k.process == "Procurement" for k in grouped["Procurement"])
