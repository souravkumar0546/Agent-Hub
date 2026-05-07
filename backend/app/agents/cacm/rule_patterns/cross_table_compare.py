"""cross_table_compare — join two tables and flag rows matching a predicate.

Use cases: 3-way match (PO vs invoice quantity), pay-to-inactive-vendor
(join AP to vendor master, flag inactive), credit-limit-exceeded (join
sales orders to customer master, flag over-limit).
"""
from __future__ import annotations

import operator
from typing import Any

from app.agents.cacm.types import ExceptionRecord, RuleContext


_OPS = {
    "==": operator.eq, "!=": operator.ne,
    ">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le,
}


def cross_table_compare(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    left = ctx.tables[params["left_table"]]
    right = ctx.tables[params["right_table"]]
    join_pairs = params["join_on"]
    flag = params["flag_when"]
    risk = params["risk"]
    reason_template = params["reason_template"]
    field_cols = params["fields"]

    # Inner-join on the supplied column pairs.
    left_keys = [p[0] for p in join_pairs]
    right_keys = [p[1] for p in join_pairs]
    joined = left.merge(right, left_on=left_keys, right_on=right_keys, suffixes=("__l", "__r"))

    side = flag["side"]  # "left" or "right" — only relevant for disambiguating same-named columns
    col = flag["column"]
    if side == "left" and col + "__l" in joined.columns:
        col_actual = col + "__l"
    elif side == "right" and col + "__r" in joined.columns:
        col_actual = col + "__r"
    else:
        col_actual = col
    op = _OPS[flag["op"]]

    flagged = joined[op(joined[col_actual], flag["value"])]

    excs: list[ExceptionRecord] = []
    for _, row in flagged.iterrows():
        excs.append(ExceptionRecord(
            exception_no="",
            risk=risk if isinstance(risk, str) else "Medium",
            reason=reason_template.format(**{c: row[c] for c in field_cols}),
            value=None,
            fields={c: row[c] for c in field_cols},
        ))
    return excs
