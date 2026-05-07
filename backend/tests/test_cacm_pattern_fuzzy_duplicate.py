"""Tests for the fuzzy_duplicate rule pattern."""
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.fuzzy_duplicate import fuzzy_duplicate
from app.agents.cacm.types import RuleContext


def test_groups_near_duplicate_rows():
    df = pd.DataFrame({
        "po_no": ["A", "B", "C", "D"],
        "vendor_code": ["V1", "V1", "V1", "V2"],
        "amount": [1000, 1000, 50, 500],
        "description": ["Beaker 250ml", "Beaker 250 ml", "Pipette tip", "Centrifuge"],
    })
    excs = fuzzy_duplicate(RuleContext(tables={"ekko": df}, kpi_type="test"), {
        "table": "ekko",
        "id_column": "po_no",
        "compare_columns": ["vendor_code", "amount", "description"],
        "threshold": 0.7,
        "risk": "Medium",
        "reason_template": "POs {ids} look like duplicates ({score:.0%} similar)",
    })
    # A and B should cluster together; C and D should not.
    assert len(excs) == 1
    assert "A" in excs[0].fields["ids"] and "B" in excs[0].fields["ids"]
    assert excs[0].risk == "Medium"


def test_no_duplicates_returns_empty():
    df = pd.DataFrame({
        "po_no": ["A", "B"],
        "vendor_code": ["V1", "V2"],
        "amount": [100, 999999],
        "description": ["Apples", "Centrifuge unit"],
    })
    excs = fuzzy_duplicate(RuleContext(tables={"ekko": df}, kpi_type="t"), {
        "table": "ekko",
        "id_column": "po_no",
        "compare_columns": ["vendor_code", "amount", "description"],
        "threshold": 0.9,
        "risk": "Medium",
        "reason_template": "x",
    })
    assert excs == []
