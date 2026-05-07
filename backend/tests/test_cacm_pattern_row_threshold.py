"""Tests for the row_threshold rule pattern."""
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.row_threshold import row_threshold
from app.agents.cacm.types import RuleContext


def _ctx(df: pd.DataFrame, name: str = "t") -> RuleContext:
    return RuleContext(tables={name: df}, kpi_type="test")


def test_flags_rows_above_threshold():
    df = pd.DataFrame({
        "doc_no": ["A", "B", "C"],
        "user": ["u1", "u2", "u3"],
        "amount": [5000, 12000, 9999],
    })
    excs = row_threshold(_ctx(df), {
        "table": "t",
        "column": "amount",
        "op": ">",
        "threshold": 10000,
        "risk": "High",
        "reason_template": "Amount {value} above {threshold}",
        "fields": ["doc_no", "user", "amount"],
    })
    assert len(excs) == 1
    assert excs[0].fields["doc_no"] == "B"
    assert excs[0].risk == "High"
    assert excs[0].value == 12000
    assert "12000" in excs[0].reason and "10000" in excs[0].reason


def test_static_risk_vs_banded_risk():
    df = pd.DataFrame({"doc_no": ["A", "B", "C"], "amount": [11000, 50000, 200000]})
    # Banded risk: list of (low, high, risk) tuples; high=None means open-ended.
    excs = row_threshold(_ctx(df), {
        "table": "t", "column": "amount", "op": ">", "threshold": 10000,
        "risk": [(0, 49999, "Low"), (50000, 99999, "Medium"), (100000, None, "High")],
        "reason_template": "Amount {value}", "fields": ["doc_no", "amount"],
    })
    risks = sorted(e.risk for e in excs)
    assert risks == ["High", "Low", "Medium"]


def test_no_exceptions_when_no_rows_match():
    df = pd.DataFrame({"doc_no": ["A"], "amount": [100]})
    excs = row_threshold(_ctx(df), {
        "table": "t", "column": "amount", "op": ">", "threshold": 10000,
        "risk": "High", "reason_template": "x", "fields": ["doc_no"],
    })
    assert excs == []


def test_unknown_op_raises():
    import pytest
    df = pd.DataFrame({"doc_no": ["A"], "amount": [100]})
    with pytest.raises(ValueError, match="op"):
        row_threshold(_ctx(df), {
            "table": "t", "column": "amount", "op": "BOGUS",
            "threshold": 10, "risk": "High", "reason_template": "x", "fields": ["doc_no"],
        })
