"""aggregate_threshold — group rows + aggregate + threshold.

Use cases: vendor concentration (top vendor share of spend > 50%), failed
logins per user > 5, write-offs per user > 10. Supports an absolute
threshold or a fraction-of-total threshold via `as_fraction=True`.

`risk` may be either a static string or a list of `(low, high, label)`
bands resolved against the per-group aggregated value — mirrors how
`row_threshold` grades severity by amount.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.agents.cacm.types import ExceptionRecord, RuleContext


_AGG_FNS = {"sum": "sum", "count": "count", "mean": "mean", "max": "max", "min": "min"}
_OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}


def _resolve_risk(spec: Any, value: float) -> str:
    """Static string passes through; band-list `[(low, high, label), ...]`
    matches the first range that contains `value` (high=None → open-ended)."""
    if isinstance(spec, str):
        return spec
    for low, high, label in spec:
        if value >= low and (high is None or value <= high):
            return label
    return "Low"


def aggregate_threshold(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    df = ctx.tables[params["table"]]
    group_by = params["group_by"]
    agg_col = params["agg"]["column"]
    agg_fn = _AGG_FNS[params["agg"]["fn"]]
    op = _OPS[params["op"]]
    threshold = float(params["threshold"])
    as_fraction = bool(params.get("as_fraction", False))
    risk = params["risk"]
    reason_template = params["reason_template"]

    grouped = df.groupby(group_by)[agg_col].agg(agg_fn)
    total = float(grouped.sum()) if as_fraction else None

    excs: list[ExceptionRecord] = []
    for key, value in grouped.items():
        v = float(value)
        compare = (v / total) if as_fraction and total else v
        if not op(compare, threshold):
            continue
        key_repr = key if not isinstance(key, tuple) else " / ".join(str(x) for x in key)
        fraction = (v / total) if total else None
        excs.append(ExceptionRecord(
            exception_no="",
            risk=_resolve_risk(risk, v),
            reason=reason_template.format(key=key_repr, value=v, fraction=fraction or 0),
            value=v,
            fields={"key": key_repr, "agg_value": v, "fraction": fraction},
        ))
    return excs
