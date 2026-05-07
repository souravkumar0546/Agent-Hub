"""temporal_anomaly — date-based anomaly detection (weekend/holiday/ageing).

Modes:
  weekend  — flag rows whose date weekday ∈ {weekday_set}
  stale    — flag rows whose date < reference_date - days
  ageing   — flag every row, but bucket risk by age (used with always-flag KPIs like aged claims)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from app.agents.cacm.types import ExceptionRecord, RuleContext


_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def temporal_anomaly(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    df = ctx.tables[params["table"]]
    col = params["date_column"]
    mode = params["mode"]
    mp = params["params"]
    risk_default = params["risk"]
    reason_template = params["reason_template"]
    field_cols = params["fields"]

    if mode == "weekend":
        weekday_set = set(mp["weekday_set"])
        flagged = df[df[col].dt.weekday.isin(weekday_set)]
        excs = [
            ExceptionRecord(
                exception_no="", risk=risk_default,
                reason=reason_template.format(date=row[col].date(), weekday=_WEEKDAYS[row[col].weekday()],
                                              **{c: row[c] for c in field_cols}),
                value=None,
                fields={c: row[c] for c in field_cols},
            )
            for _, row in flagged.iterrows()
        ]
        return excs

    if mode == "stale":
        ref = pd.to_datetime(mp["reference_date"])
        cutoff = ref - pd.Timedelta(days=int(mp["days"]))
        flagged = df[df[col] < cutoff]
        return [
            ExceptionRecord(
                exception_no="", risk=risk_default,
                reason=reason_template.format(**{c: row[c] for c in field_cols}),
                value=float((ref - row[col]).days),
                fields={c: row[c] for c in field_cols},
            )
            for _, row in flagged.iterrows()
        ]

    if mode == "ageing":
        ref = pd.to_datetime(mp["reference_date"])
        buckets = mp["buckets"]   # [(low_days, high_days, risk)]
        excs: list[ExceptionRecord] = []
        for _, row in df.iterrows():
            age_days = int((ref - row[col]).days)
            risk = risk_default
            for low, high, r in buckets:
                if age_days >= low and (high is None or age_days <= high):
                    risk = r
                    break
            excs.append(ExceptionRecord(
                exception_no="", risk=risk,
                reason=reason_template.format(age_days=age_days, **{c: row[c] for c in field_cols}),
                value=float(age_days),
                fields={**{c: row[c] for c in field_cols}, "age_days": age_days},
            ))
        return excs

    raise ValueError(f"temporal_anomaly: unknown mode {mode!r}")
