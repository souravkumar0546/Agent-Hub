from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.cross_table_compare import cross_table_compare
from app.agents.cacm.types import RuleContext


def test_flags_join_with_predicate():
    rbkp = pd.DataFrame({
        "inv_no": ["I1", "I2", "I3"],
        "vendor_code": ["V1", "V2", "V3"],
        "amount": [1000, 500, 2000],
    })
    lfa1 = pd.DataFrame({"vendor_code": ["V1", "V2", "V3"], "is_active": [True, False, True]})
    excs = cross_table_compare(RuleContext(tables={"rbkp": rbkp, "lfa1": lfa1}, kpi_type="t"), {
        "left_table": "rbkp",
        "right_table": "lfa1",
        "join_on": [("vendor_code", "vendor_code")],
        "flag_when": {"column": "is_active", "op": "==", "value": False, "side": "right"},
        "risk": "High",
        "reason_template": "Invoice {inv_no} paid to inactive vendor {vendor_code}",
        "fields": ["inv_no", "vendor_code", "amount"],
    })
    assert len(excs) == 1
    assert excs[0].fields["inv_no"] == "I2"
    assert excs[0].risk == "High"
