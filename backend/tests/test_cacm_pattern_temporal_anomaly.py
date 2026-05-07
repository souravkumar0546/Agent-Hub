from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.temporal_anomaly import temporal_anomaly
from app.agents.cacm.types import RuleContext


def test_weekend_mode_flags_saturday_sunday():
    df = pd.DataFrame({
        "doc_no": ["D1", "D2", "D3"],
        "user": ["u1", "u2", "u3"],
        "posting_date": pd.to_datetime(["2026-05-02", "2026-05-04", "2026-05-03"]),  # Sat, Mon, Sun
    })
    excs = temporal_anomaly(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "date_column": "posting_date",
        "mode": "weekend",
        "params": {"weekday_set": [5, 6]},
        "risk": "Medium",
        "reason_template": "Posting on {date} ({weekday})",
        "fields": ["doc_no", "user", "posting_date"],
    })
    assert {e.fields["doc_no"] for e in excs} == {"D1", "D3"}


def test_stale_mode_flags_old_dates():
    df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "last_login": pd.to_datetime(["2025-12-01", "2026-04-15"]),
    })
    excs = temporal_anomaly(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "date_column": "last_login",
        "mode": "stale",
        "params": {"days": 90, "reference_date": "2026-05-07"},
        "risk": "High",
        "reason_template": "User {user_id} dormant since {last_login}",
        "fields": ["user_id", "last_login"],
    })
    assert len(excs) == 1
    assert excs[0].fields["user_id"] == "u1"
