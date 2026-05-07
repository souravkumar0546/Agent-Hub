from __future__ import annotations

import dataclasses
import json

import pandas as pd
import pytest

from app.agents.cacm.types import (
    KpiDef, RuleContext, ExceptionRecord,
)


def test_kpidef_minimum_fields():
    kpi = KpiDef(
        type="po_after_invoice",
        process="Procurement",
        name="PO After Invoice",
        description="…",
        rule_objective="…",
        source_tables=["EKKO", "RBKP"],
        pattern="date_compare",
        params={"foo": "bar"},
    )
    assert kpi.type == "po_after_invoice"
    assert kpi.params == {"foo": "bar"}


def test_rulecontext_holds_dataframes():
    df = pd.DataFrame({"a": [1, 2]})
    ctx = RuleContext(tables={"ekko": df}, kpi_type="x")
    assert "ekko" in ctx.tables
    assert ctx.kpi_type == "x"


def test_exception_record_to_payload():
    e = ExceptionRecord(
        exception_no="EX-0001",
        risk="High",
        reason="…",
        value=12345.0,
        fields={"po_no": "4500001234", "vendor_code": "V001"},
    )
    payload = e.to_payload()
    assert payload["exception_no"] == "EX-0001"
    assert payload["risk"] == "High"
    assert payload["fields"]["po_no"] == "4500001234"


def test_kpidef_is_frozen():
    """KpiDef instances should be immutable so the catalog can't drift at runtime."""
    kpi = KpiDef(
        type="x", process="p", name="n", description="d",
        rule_objective="r", source_tables=[], pattern="row_threshold", params={},
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        kpi.type = "y"  # type: ignore[misc]


def test_exception_record_fields_default_factory_isolates_instances():
    """Guards against the classic mutable-default-argument bug. Two records
    instantiated with the default `fields` value must NOT share the same dict."""
    a = ExceptionRecord(exception_no="EX-1", risk="High", reason="r")
    b = ExceptionRecord(exception_no="EX-2", risk="High", reason="r")
    a.fields["k"] = 1
    assert b.fields == {}


def test_to_payload_is_json_serializable():
    """payload is stored in cacm_exceptions.payload_json — it must JSON-encode
    cleanly when value is None and fields is empty."""
    e = ExceptionRecord(exception_no="EX-0001", risk="High", reason="r")
    json.dumps(e.to_payload())  # must not raise
