from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.aggregate_threshold import aggregate_threshold
from app.agents.cacm.types import RuleContext


def test_flags_groups_above_absolute_threshold():
    df = pd.DataFrame({"user": ["u1", "u1", "u2"], "doc": ["a", "b", "c"]})
    excs = aggregate_threshold(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "group_by": ["user"],
        "agg": {"column": "doc", "fn": "count"},
        "op": ">", "threshold": 1, "as_fraction": False,
        "risk": "Medium",
        "reason_template": "User {key} has {value} entries",
        "fields": [],
    })
    assert len(excs) == 1
    assert excs[0].fields["key"] == "u1"


def test_band_list_resolves_risk_per_group():
    """When `risk` is a list of (low, high, label) bands, grade each
    flagged group's risk by its aggregated value — mirrors row_threshold."""
    df = pd.DataFrame({
        "material": ["M1"] * 5 + ["M2"] * 8 + ["M3"] * 12,
        "doc": list("abcdefghijklmnopqrstuvwxy"),
    })
    excs = aggregate_threshold(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "group_by": ["material"],
        "agg": {"column": "doc", "fn": "count"},
        "op": ">", "threshold": 3, "as_fraction": False,
        "risk": [(4, 5, "Low"), (6, 9, "Medium"), (10, None, "High")],
        "reason_template": "{key} = {value:.0f}",
        "fields": [],
    })
    by_key = {e.fields["key"]: e for e in excs}
    assert by_key["M1"].risk == "Low"     # value=5
    assert by_key["M2"].risk == "Medium"  # value=8
    assert by_key["M3"].risk == "High"    # value=12


def test_flags_fraction_of_total():
    df = pd.DataFrame({"vendor": ["A", "A", "A", "B"], "amount": [100, 100, 100, 50]})
    # Total spend = 350; vendor A = 300 (~86%). Threshold 0.5 → A flagged.
    excs = aggregate_threshold(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "group_by": ["vendor"],
        "agg": {"column": "amount", "fn": "sum"},
        "op": ">", "threshold": 0.5, "as_fraction": True,
        "risk": "High",
        "reason_template": "{key} = {fraction:.0%}",
        "fields": [],
    })
    assert len(excs) == 1
    assert excs[0].fields["key"] == "A"
    assert "86%" in excs[0].reason


def test_metadata_fields_projection_picks_latest_by_posting_date():
    """Optional `metadata_fields` projects representative-row columns
    into each exception's `fields`, and lets the reason template splat
    those values too. Latest `posting_date` wins."""
    df = pd.DataFrame({
        "material_id": ["M1", "M1", "M1", "M1", "M2"],
        "doc_no": ["d1", "d2", "d3", "d4", "d5"],
        "material_name": ["Acme Widget"] * 4 + ["Other"],
        "posting_date": pd.to_datetime([
            "2026-01-01", "2026-04-01", "2026-02-15", "2026-03-10", "2026-04-02",
        ]),
        "movement_type": ["561", "562", "701", "702", "309"],
    })
    excs = aggregate_threshold(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "group_by": ["material_id"],
        "agg": {"column": "doc_no", "fn": "count"},
        "op": ">", "threshold": 3, "as_fraction": False,
        "risk": "High",
        "reason_template": "Material {material_id} ({material_name}) has {value:.0f} adjustments",
        "fields": [],
        "metadata_fields": ["material_id", "material_name", "movement_type", "posting_date"],
    })
    assert len(excs) == 1
    e = excs[0]
    # Representative row is the latest posting_date (2026-04-01 → movement_type 562)
    assert e.fields["material_id"] == "M1"
    assert e.fields["material_name"] == "Acme Widget"
    assert e.fields["movement_type"] == "562"
    assert e.fields["posting_date"] == "2026-04-01"
    # Aggregated bookkeeping still in fields
    assert e.fields["agg_value"] == 4
    # Reason template was given the metadata kwargs
    assert "Acme Widget" in e.reason
    assert "M1" in e.reason


def test_metadata_fields_absent_keeps_legacy_behavior():
    """No metadata_fields → behaviour identical to before this change."""
    df = pd.DataFrame({"user": ["u1", "u1", "u2"], "doc": ["a", "b", "c"]})
    excs = aggregate_threshold(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "group_by": ["user"],
        "agg": {"column": "doc", "fn": "count"},
        "op": ">", "threshold": 1, "as_fraction": False,
        "risk": "Medium",
        "reason_template": "User {key} has {value} entries",
        "fields": [],
    })
    assert len(excs) == 1
    # No extra metadata keys leaked into the exception payload.
    assert set(excs[0].fields.keys()) == {"key", "agg_value", "fraction"}
