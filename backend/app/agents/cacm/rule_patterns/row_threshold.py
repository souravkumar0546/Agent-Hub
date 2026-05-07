"""row_threshold — flag rows where a column compares against a threshold.

Used by KPIs that boil down to "value > X": Manual JE above threshold,
Round-sum invoice amounts, Cycle count variances, etc.

`risk` may be either a static string ("High"/"Medium"/"Low") or a list of
`(low, high, risk)` bands so the same rule can rate exceptions by severity
(e.g. amount in $10k–$50k = Low, $50k–$100k = Medium, >$100k = High).
"""
from __future__ import annotations

import operator
from typing import Any

from app.agents.cacm.types import ExceptionRecord, RuleContext


_OPS = {
    ">": operator.gt, ">=": operator.ge,
    "<": operator.lt, "<=": operator.le,
    "==": operator.eq, "!=": operator.ne,
}


def _resolve_risk(risk_spec: Any, value: float) -> str:
    if isinstance(risk_spec, str):
        return risk_spec
    # banded: list[(low, high, risk)] — high=None → open-ended
    for low, high, risk in risk_spec:
        if value >= low and (high is None or value <= high):
            return risk
    return "Low"


def row_threshold(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    table = params["table"]
    column = params["column"]
    op = params["op"]
    threshold = params["threshold"]
    risk_spec = params["risk"]
    reason_template = params["reason_template"]
    field_cols = params["fields"]

    if op not in _OPS:
        raise ValueError(f"row_threshold: unknown op {op!r}; must be one of {list(_OPS)}")

    df = ctx.tables[table]
    op_fn = _OPS[op]

    excs: list[ExceptionRecord] = []
    for _, row in df[op_fn(df[column], threshold)].iterrows():
        value = float(row[column])
        excs.append(ExceptionRecord(
            exception_no="",  # assigned by orchestrator after the full list is collected
            risk=_resolve_risk(risk_spec, value),
            reason=reason_template.format(value=value, threshold=threshold),
            value=value,
            fields={c: row[c] for c in field_cols},
        ))
    return excs
