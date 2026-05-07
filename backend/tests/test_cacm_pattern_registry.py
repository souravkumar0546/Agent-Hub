"""Catches a forgotten registration — every pattern file must show up in PATTERN_REGISTRY."""
from __future__ import annotations

from app.agents.cacm.rule_patterns import PATTERN_REGISTRY


EXPECTED = {
    "row_threshold", "fuzzy_duplicate", "date_compare",
    "aggregate_threshold", "cross_table_compare",
    "missing_reference", "temporal_anomaly",
}


def test_all_seven_patterns_registered():
    assert set(PATTERN_REGISTRY) == EXPECTED


def test_every_pattern_is_callable():
    for name, fn in PATTERN_REGISTRY.items():
        assert callable(fn), f"{name} is not callable"
