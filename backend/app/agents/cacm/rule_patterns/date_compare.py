"""date_compare — flag rows where date_a op date_b.

Used by KPIs like "PO created after invoice posted". The diff in days drives
risk banding so a 1-day lag (administrative slip) is rated lower than a
30-day lag (likely after-the-fact PO).
"""
from __future__ import annotations

import operator
from typing import Any

import pandas as pd

from app.agents.cacm.types import ExceptionRecord, RuleContext


_OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def _json_safe(v: Any) -> Any:
    """Coerce pandas / numpy scalars into something JSON-serializable.

    Field payloads are persisted as JSON; Timestamp / numpy ints leak in
    when we surface columns from the joined DataFrame.
    """
    if v is None:
        return None
    # NaT is a Timestamp subclass on some pandas versions, but `isinstance`
    # against Timestamp covers it. Either way, pd.isna handles NaT/NaN/None.
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    # numpy scalars expose .item() to get a native Python type.
    if hasattr(v, "item") and not isinstance(v, str):
        try:
            return v.item()
        except (ValueError, TypeError):
            pass
    return v


def date_compare(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    df = ctx.tables[params["table"]]
    left = params["left_date"]
    right = params["right_date"]
    op = _OPS[params["op"]]
    bands = params["risk_bands"]
    reason_template = params["reason_template"]
    field_cols = params["fields"]

    excs: list[ExceptionRecord] = []
    flagged = df[op(df[left], df[right])]
    for _, row in flagged.iterrows():
        diff_days = abs(int((row[left] - row[right]).days))
        risk = "Low"
        for low, high, r in bands:
            if diff_days >= low and (high is None or diff_days <= high):
                risk = r
                break
        # Build the JSON-safe field map up front; use it both for the reason
        # template and the persisted payload so both see the same values.
        safe_fields = {c: _json_safe(row[c]) for c in field_cols if c in row.index}
        excs.append(ExceptionRecord(
            exception_no="",
            risk=risk,
            reason=reason_template.format(diff_days=diff_days, **safe_fields),
            value=float(diff_days),
            fields={**safe_fields, "diff_days": diff_days},
        ))
    return excs
