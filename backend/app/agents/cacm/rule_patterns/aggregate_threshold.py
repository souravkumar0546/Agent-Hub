"""aggregate_threshold — group rows + aggregate + threshold.

Use cases: vendor concentration (top vendor share of spend > 50%), failed
logins per user > 5, write-offs per user > 10. Supports an absolute
threshold or a fraction-of-total threshold via `as_fraction=True`.

`risk` may be either a static string or a list of `(low, high, label)`
bands resolved against the per-group aggregated value — mirrors how
`row_threshold` grades severity by amount.

Optional `metadata_fields` projects per-group representative-row columns
into each exception's `fields` payload. The representative row is the
latest row by `posting_date` if that column exists, otherwise the first
row in the group. Useful when the KPI's exception report needs richer
context (material name, plant, document number, etc.) than just the
group key + aggregated count.
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


def _json_safe(v: Any) -> Any:
    """Coerce pandas / numpy scalars into something JSON-serializable.

    Mirrors `date_compare._json_safe` — exception payloads are persisted
    as JSON, so Timestamps / numpy ints / NaN/NaT need normalising.
    """
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, pd.Timestamp):
        return v.strftime("%Y-%m-%d")
    if hasattr(v, "item") and not isinstance(v, str):
        try:
            return v.item()
        except (ValueError, TypeError):
            pass
    return v


def _representative_row(group_df: pd.DataFrame) -> pd.Series:
    """Pick the row that best represents a group — latest posting_date if
    available, otherwise first row. Returns a copy so callers can safely
    project columns out of it.
    """
    if "posting_date" in group_df.columns and len(group_df) > 0:
        try:
            sorted_df = group_df.sort_values("posting_date", ascending=False, kind="stable")
            return sorted_df.iloc[0]
        except (TypeError, ValueError):
            pass
    return group_df.iloc[0]


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
    metadata_fields: list[str] = list(params.get("metadata_fields") or [])

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

        # Per-group metadata projection: surface a representative row's
        # values for each requested column. The rule still aggregates,
        # but the exception payload now carries enough per-group context
        # for the rich exception report.
        meta: dict[str, Any] = {}
        if metadata_fields:
            # Match the group rows. groupby key may be scalar or tuple
            # depending on whether group_by has 1 or N columns.
            if isinstance(key, tuple):
                mask = pd.Series(True, index=df.index)
                for col, val in zip(group_by, key):
                    mask &= (df[col] == val)
            else:
                mask = (df[group_by[0]] == key)
            sub = df[mask]
            if len(sub) > 0:
                rep = _representative_row(sub)
                for col in metadata_fields:
                    if col in rep.index:
                        meta[col] = _json_safe(rep[col])

        # `reason_template.format(...)` gets the original keys plus any
        # metadata field values, so templates can reference e.g.
        # `{material_id}` / `{material_name}`.
        format_kwargs: dict[str, Any] = {
            "key": key_repr,
            "value": v,
            "fraction": fraction or 0,
            **meta,
        }

        excs.append(ExceptionRecord(
            exception_no="",
            risk=_resolve_risk(risk, v),
            reason=reason_template.format(**format_kwargs),
            value=v,
            fields={"key": key_repr, "agg_value": v, "fraction": fraction, **meta},
        ))
    return excs
