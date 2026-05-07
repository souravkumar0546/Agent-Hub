"""missing_reference — anti-join: rows in left table whose key is not present in right table.

Use cases: PO without contract, invoice without PO, salary change without
HR approval. Treats null/blank left-key as "missing" too.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.agents.cacm.types import ExceptionRecord, RuleContext


def missing_reference(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    left = ctx.tables[params["left_table"]]
    right = ctx.tables[params["right_table"]]
    left_key = params["left_key"]
    right_key = params["right_key"]
    risk = params["risk"]
    reason_template = params["reason_template"]
    field_cols = params["fields"]

    # Anti-join: rows whose left_key is null OR not in right_key set.
    valid_keys = set(right[right_key].dropna().astype(str))
    mask_null = left[left_key].isna() | (left[left_key].astype(str) == "")
    mask_unmatched = ~left[left_key].astype(str).isin(valid_keys)
    flagged = left[mask_null | mask_unmatched]

    excs: list[ExceptionRecord] = []
    for _, row in flagged.iterrows():
        excs.append(ExceptionRecord(
            exception_no="",
            risk=risk if isinstance(risk, str) else "Medium",
            reason=reason_template.format(**{c: row[c] for c in field_cols}),
            value=None,
            fields={c: (None if pd.isna(row[c]) else row[c]) for c in field_cols},
        ))
    return excs
