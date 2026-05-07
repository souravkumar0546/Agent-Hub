"""CACM pipeline orchestrator — runs the 6 stages for a single KPI run.

Stages emit progress events with `_emit(stage, message, payload?)`. Sleeps
between events make the demo feel paced (~10-15s end-to-end at default
delays). Tests inject `sleep_fn=lambda _: asyncio.sleep(0)` to skip the
theatrical pauses entirely.

The trimmed v1 catalog ships 2 KPIs (Procurement / Inventory). Process
files and derived-table builders below match that scope. Adding a new
process means: (a) drop a JSON in `sample_data/`, (b) add a key to
`_PROCESS_FILES`, (c) extend `_build_derived_tables` if the KPI needs
a logical / pre-joined table.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable

import pandas as pd
from sqlalchemy.orm import Session

from app.agents.cacm.kpi_catalog import kpi_by_type
from app.agents.cacm.recommendations import recommendation_for
from app.agents.cacm.rule_patterns import PATTERN_REGISTRY
from app.agents.cacm.types import RuleContext
from app.models.cacm import CacmException, CacmRun, CacmRunEvent


SAMPLE_DATA_DIR = Path(__file__).resolve().parent / "sample_data"

# Trimmed for v1 — only the processes whose KPIs are in the active catalog.
_PROCESS_FILES: dict[str, str] = {
    "Procurement": "procurement.json",
    "Inventory": "inventory.json",
}

# Movement types treated as "adjustments" for repeated_material_adjustments.
_ADJUSTMENT_MOVEMENT_TYPES = {"309", "561", "562", "701", "702"}


# Names that look like derived / pre-joined tables — excluded from the
# `total_records` denominator. Heuristic substrings cover the v1 derived
# tables (`po_invoice_joined`, `mseg_adjustments`) and a few likely future
# shapes (`*_with_*`).
_DERIVED_HINTS = ("_joined", "_with_", "_adjustments")


def _is_derived(name: str) -> bool:
    return any(h in name for h in _DERIVED_HINTS)


def _aging_bucket(diff_days: float | int | None) -> str:
    """Map a PO/invoice date diff onto a coarse delay-category label.

    Mirrors the procurement risk_bands shape (0-3 / 4-14 / 15+) but framed
    as an audit-friendly "Up to 3 days / 4-14 days / 15+ days" string.
    Returns an empty string for missing/non-numeric input.
    """
    if diff_days is None:
        return ""
    try:
        d = float(diff_days)
    except (TypeError, ValueError):
        return ""
    if d < 0:
        return ""
    if d <= 3:
        return "Up to 3 days"
    if d <= 14:
        return "4-14 days"
    return "15+ days"


def _enrich_exception_fields(process: str, fields: dict[str, Any]) -> dict[str, Any]:
    """Domain-specific post-processing of an exception's `fields` payload.

    Procurement exceptions get an `aging_bucket` derived from `diff_days`.
    Other processes pass through unchanged.
    """
    if process == "Procurement":
        fields = {**fields, "aging_bucket": _aging_bucket(fields.get("diff_days"))}
    return fields


def _load_sample(process: str) -> dict[str, pd.DataFrame]:
    path = SAMPLE_DATA_DIR / _PROCESS_FILES[process]
    raw = json.loads(path.read_text())
    return {name: pd.DataFrame(rows) for name, rows in raw.items()}


def _date_columns(tables: dict[str, pd.DataFrame]) -> None:
    """Cast obvious date columns to datetime in-place. Sample JSON stores
    dates as ISO strings; rules expect Timestamp.

    Heuristic skips columns ending in `_by` or `_id` (which would otherwise
    catch `po_created_by` / `created_id`) and columns ending in `_no`.
    """
    date_hints = ("date", "_at", "posted", "created", "login", "termination")
    skip_suffixes = ("_by", "_id", "_no", "_code", "_status")
    for df in tables.values():
        for col in df.columns:
            lc = col.lower()
            if any(lc.endswith(s) for s in skip_suffixes):
                continue
            if any(hint in lc for hint in date_hints):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass


def _build_derived_tables(
    process: str, tables: dict[str, pd.DataFrame]
) -> dict[str, pd.DataFrame]:
    """Build pre-joined / filtered logical tables that KPI patterns reference.

    Keeps the rule-pattern signatures simple: a pattern asks for one
    table by name; the orchestrator does the joining once.
    """
    derived: dict[str, pd.DataFrame] = {}

    if process == "Procurement":
        if "ekko" in tables and "rbkp" in tables:
            # Pull every column the exception report wants surfaced. Falls
            # back gracefully if a column is absent (older sample data).
            ekko_cols = [
                c for c in [
                    "po_no", "vendor_code", "po_created", "company_code",
                    "location", "po_line_item", "po_amount", "po_created_by",
                    "po_approval_status",
                ] if c in tables["ekko"].columns
            ]
            rbkp_cols = [
                c for c in [
                    "inv_no", "po_ref", "invoice_posted", "invoice_amount",
                    "invoice_created_by",
                ] if c in tables["rbkp"].columns
            ]
            ekko = tables["ekko"][ekko_cols]
            rbkp = tables["rbkp"][rbkp_cols]
            j = ekko.merge(
                rbkp, how="inner", left_on="po_no", right_on="po_ref"
            )
            # Surface canonical column names the rule expects + the rich
            # payload columns. Drop the join-key duplicate so downstream
            # consumers don't see `po_ref` everywhere.
            keep = [c for c in j.columns if c != "po_ref"]
            derived["po_invoice_joined"] = j[keep].copy()

    if process == "Inventory":
        if "mseg" in tables:
            mseg = tables["mseg"]
            adj = mseg[
                mseg["movement_type"].astype(str).isin(_ADJUSTMENT_MOVEMENT_TYPES)
            ].copy()
            # Left-join MARA on material_id so the rule pattern can project
            # material_name / material_group into each per-material exception
            # payload. MSEG already carries unit_of_measure as the per-txn UoM —
            # rename the MARA column on collision so MSEG's wins.
            if "mara" in tables:
                mara = tables["mara"].copy()
                mara_cols = [c for c in mara.columns if c != "material_id"]
                rename_map = {
                    c: f"mara_{c}" for c in mara_cols if c in adj.columns
                }
                if rename_map:
                    mara = mara.rename(columns=rename_map)
                adj = adj.merge(mara, how="left", on="material_id")
            derived["mseg_adjustments"] = adj

    return derived


async def _emit(
    db: Session,
    run_id: int,
    seq: int,
    stage: str,
    message: str,
    payload: dict[str, Any] | None = None,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
    pause: float = 0.4,
) -> int:
    db.add(CacmRunEvent(run_id=run_id, seq=seq, stage=stage, message=message, payload_json=payload))
    db.commit()
    await sleep_fn(pause)
    return seq + 1


async def run_pipeline(
    db: Session,
    run_id: int,
    sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> None:
    """Execute the 6 stages for the given run. Persists events + exceptions.

    Re-raises on failure after marking the run `failed` and writing the
    error message — callers (the FastAPI background task) swallow the
    exception so a runtime error doesn't blow up the request handler.
    """
    run = db.get(CacmRun, run_id)
    if run is None:
        raise ValueError(f"unknown run_id {run_id}")

    kpi = kpi_by_type(run.kpi_type)
    if kpi is None:
        run.status = "failed"
        run.error_message = f"unknown kpi_type {run.kpi_type!r}"
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        return

    seq = 1
    try:
        # ── Stage 1: Extract ───────────────────────────────────────────────
        seq = await _emit(
            db, run_id, seq, "extract",
            "Connecting to SAP source system...",
            sleep_fn=sleep_fn, pause=0.4,
        )
        for tbl in kpi.source_tables:
            seq = await _emit(
                db, run_id, seq, "extract", f"Extracting from {tbl}...",
                sleep_fn=sleep_fn, pause=0.3,
            )
        tables = _load_sample(run.process)
        seq = await _emit(
            db, run_id, seq, "extract",
            f"Validating extracted records — {sum(len(t) for t in tables.values())} rows total",
            sleep_fn=sleep_fn, pause=0.4,
        )

        # ── Stage 2: Transform ─────────────────────────────────────────────
        seq = await _emit(
            db, run_id, seq, "transform",
            "Cleansing nulls and trimming whitespace...",
            sleep_fn=sleep_fn, pause=0.4,
        )
        for df in tables.values():
            for c in df.select_dtypes(include="object").columns:
                df[c] = df[c].fillna("").astype(str).str.strip()
        _date_columns(tables)
        seq = await _emit(
            db, run_id, seq, "transform",
            "Standardizing vendor codes and date formats...",
            sleep_fn=sleep_fn, pause=0.4,
        )
        derived = _build_derived_tables(run.process, tables)
        tables.update(derived)
        seq = await _emit(
            db, run_id, seq, "transform",
            "Transformation complete — source data cleansed and prepared for rule execution.",
            sleep_fn=sleep_fn, pause=0.4,
        )

        # ── Stage 3: Load ──────────────────────────────────────────────────
        seq = await _emit(
            db, run_id, seq, "load",
            "Loading transformed data into CCM data mart...",
            sleep_fn=sleep_fn, pause=0.4,
        )
        seq = await _emit(
            db, run_id, seq, "load", "Data load completed successfully.",
            sleep_fn=sleep_fn, pause=0.3,
        )

        # ── Stage 4: Rule engine ───────────────────────────────────────────
        seq = await _emit(
            db, run_id, seq, "rules",
            f"Rule engine started for KPI: {kpi.name}",
            sleep_fn=sleep_fn, pause=0.4,
        )
        seq = await _emit(
            db, run_id, seq, "rules",
            f"Reading KPI configuration (pattern={kpi.pattern})",
            sleep_fn=sleep_fn, pause=0.3,
        )
        pattern_fn = PATTERN_REGISTRY[kpi.pattern]
        ctx = RuleContext(tables=tables, kpi_type=kpi.type)
        records = pattern_fn(ctx, kpi.params)
        seq = await _emit(
            db, run_id, seq, "rules",
            f"Rule execution complete — {len(records)} candidate exceptions",
            sleep_fn=sleep_fn, pause=0.4,
        )

        # ── Stage 5: Exceptions ────────────────────────────────────────────
        seq = await _emit(
            db, run_id, seq, "exceptions",
            f"Generating exception records — {len(records)} exceptions identified",
            sleep_fn=sleep_fn, pause=0.4,
        )
        rec_text = recommendation_for(kpi.type)
        # Total = sum of base table row counts. Exclude derived/joined tables
        # so the exception_pct denominator matches the user's mental model
        # ("we extracted N rows from SAP, M came back as exceptions").
        total_records = sum(len(t) for name, t in tables.items() if not _is_derived(name))
        for i, rec in enumerate(records, start=1):
            rec.exception_no = f"EX-{i:04d}"
            payload = rec.to_payload()
            payload["fields"] = _enrich_exception_fields(run.process, payload.get("fields") or {})
            payload["recommended_action"] = rec_text
            db.add(CacmException(
                run_id=run_id,
                exception_no=rec.exception_no,
                risk=rec.risk,
                payload_json=payload,
            ))
        db.commit()

        # ── Stage 6: Dashboard ─────────────────────────────────────────────
        seq = await _emit(
            db, run_id, seq, "dashboard",
            "Computing dashboard metrics...",
            sleep_fn=sleep_fn, pause=0.4,
        )
        run.total_records = total_records
        run.total_exceptions = len(records)
        run.exception_pct = (len(records) / total_records * 100.0) if total_records else 0.0
        risk_counts: dict[str, int] = {}
        for r in records:
            risk_counts[r.risk] = risk_counts.get(r.risk, 0) + 1
        run.summary_json = {"risk_counts": risk_counts}
        run.status = "succeeded"
        run.completed_at = datetime.now(timezone.utc)
        seq = await _emit(
            db, run_id, seq, "dashboard", "Dashboard ready.",
            sleep_fn=sleep_fn, pause=0.3,
        )
        db.commit()
    except Exception as exc:  # noqa: BLE001 — orchestrator must catch broad
        run.status = "failed"
        run.error_message = repr(exc)[:500]
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise
