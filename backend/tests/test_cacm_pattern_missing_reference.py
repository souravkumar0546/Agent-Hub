from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.missing_reference import missing_reference
from app.agents.cacm.types import RuleContext


def test_flags_left_rows_without_match():
    ekko = pd.DataFrame({
        "po_no": ["P1", "P2", "P3"],
        "vendor_code": ["V1", "V2", "V3"],
        "amount": [100, 200, 300],
        "contract_ref": ["C1", None, "C3"],
    })
    contracts = pd.DataFrame({"contract_id": ["C1", "C2"]})
    excs = missing_reference(RuleContext(tables={"ekko": ekko, "contracts": contracts}, kpi_type="t"), {
        "left_table": "ekko",
        "right_table": "contracts",
        "left_key": "contract_ref",
        "right_key": "contract_id",
        "risk": "Medium",
        "reason_template": "PO {po_no} has no matching contract",
        "fields": ["po_no", "vendor_code", "amount"],
    })
    flagged_pos = {e.fields["po_no"] for e in excs}
    assert flagged_pos == {"P2", "P3"}  # P2 has null ref; P3 has C3 which isn't in contracts
