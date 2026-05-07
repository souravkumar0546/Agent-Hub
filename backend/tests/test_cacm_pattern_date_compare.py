from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.date_compare import date_compare
from app.agents.cacm.types import RuleContext


def test_flags_when_left_date_after_right_date():
    df = pd.DataFrame({
        "po_no": ["P1", "P2", "P3"],
        "inv_no": ["I1", "I2", "I3"],
        "vendor_code": ["V1", "V2", "V3"],
        "po_created": pd.to_datetime(["2026-04-15", "2026-04-01", "2026-04-30"]),
        "invoice_posted": pd.to_datetime(["2026-04-10", "2026-04-15", "2026-04-29"]),
    })
    excs = date_compare(RuleContext(tables={"j": df}, kpi_type="t"), {
        "table": "j",
        "left_date": "po_created",
        "right_date": "invoice_posted",
        "op": ">",
        "risk_bands": [(0, 3, "Low"), (4, 14, "Medium"), (15, None, "High")],
        "reason_template": "PO {po_no} created {diff_days} days after invoice {inv_no}",
        "fields": ["po_no", "inv_no", "vendor_code"],
    })
    # P1 is 5 days late → Medium; P3 is 1 day late → Low; P2 is on-time (PO before inv).
    assert {e.fields["po_no"] for e in excs} == {"P1", "P3"}
    by_po = {e.fields["po_no"]: e for e in excs}
    assert by_po["P1"].risk == "Medium"
    assert by_po["P3"].risk == "Low"
    assert "5 days after" in by_po["P1"].reason
