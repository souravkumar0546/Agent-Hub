"""CACM API — KPI catalog browse, run lifecycle, exception reporting, dashboard.

Route layout:
  GET    /api/cacm/library                                 — process+KPI catalog
  POST   /api/cacm/runs                                    — start a run (background pipeline)
  GET    /api/cacm/runs                                    — list runs for current org
  GET    /api/cacm/runs/{id}                               — run summary
  GET    /api/cacm/runs/{id}/events?since=N                — short-poll for events past cursor N
  GET    /api/cacm/runs/{id}/exceptions[?risk=...]         — list exceptions, optional risk filter
  GET    /api/cacm/runs/{id}/exceptions.csv                — CSV download
  GET    /api/cacm/runs/{id}/exceptions.xlsx               — Excel download (openpyxl)
  GET    /api/cacm/runs/{id}/dashboard                     — by_risk / by_company / by_vendor / monthly_trend
  GET    /api/cacm/runs/{id}/stage/extraction              — extracted source tables (wizard)
  GET    /api/cacm/runs/{id}/stage/transformation          — transformation rules + derived tables
  GET    /api/cacm/runs/{id}/stage/loading                 — CCM data-mart load summary
  GET    /api/cacm/runs/{id}/stage/rule-engine             — KPI rule conditions + run totals
  GET    /api/cacm/runs/{id}/stage/extraction/download/{table_name}.csv — CSV per table

The pipeline runs as an asyncio background task started inside POST /runs.
We open a fresh `SessionLocal()` inside `_run_in_background` rather than
sharing the request-scoped Session — that one is closed by FastAPI as
soon as the handler returns.
"""
from __future__ import annotations

import asyncio
import csv
import io
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.agents.cacm.kpi_catalog import kpi_by_type, kpis_by_process
from app.agents.cacm.process_catalog import get_process, get_processes
from app.agents.cacm.service import (
    SAMPLE_DATA_DIR,
    _PROCESS_FILES,
    _build_derived_tables,
    _date_columns,
    run_pipeline,
)
from app.api.deps import OrgContext, get_db, require_org
from app.models.cacm import CacmException, CacmRun, CacmRunEvent
from app.schemas.cacm import (
    DerivedTableSummary,
    EventsResponse,
    ExceptionItem,
    ExceptionsResponse,
    ExtractedTable,
    ExtractionStageResponse,
    KpiSummary,
    KriSummary,
    LibraryResponse,
    LoadedTable,
    LoadingStageResponse,
    ProcessDef,
    ProcessesResponse,
    ProcessGroup,
    RuleEngineStageResponse,
    RunEvent,
    RunSummary,
    StartRunRequest,
    StartRunResponse,
    TransformationStageResponse,
)


router = APIRouter(prefix="/cacm", tags=["cacm"])


# Stale-run threshold: a run still marked `running` after this elapsed
# time is treated as crashed and lazily flipped to `failed` on the next
# events poll. The orchestrator's normal sleeps total ~10-15s so 5
# minutes is safely above the demo runtime.
_STALE_AFTER = timedelta(minutes=5)


# ── Library ──────────────────────────────────────────────────────────────────


@router.get("/library", response_model=LibraryResponse)
def get_library(_: OrgContext = Depends(require_org)) -> LibraryResponse:
    out: list[ProcessGroup] = []
    for proc, kpis in kpis_by_process().items():
        out.append(ProcessGroup(
            name=proc,
            kpis=[KpiSummary(
                type=k.type,
                name=k.name,
                description=k.description,
                rule_objective=k.rule_objective,
                pattern=k.pattern,
                source_tables=k.source_tables,
            ) for k in kpis],
        ))
    return LibraryResponse(processes=out)


# ── Process catalog (Process Picker) ─────────────────────────────────────────


def _serialize_process(p) -> ProcessDef:
    return ProcessDef(
        key=p.key,
        name=p.name,
        intro=p.intro,
        kris=[KriSummary(name=k.name, kpi_type=k.kpi_type) for k in p.kris],
    )


@router.get("/processes", response_model=ProcessesResponse)
def list_processes(_: OrgContext = Depends(require_org)) -> ProcessesResponse:
    return ProcessesResponse(processes=[_serialize_process(p) for p in get_processes()])


@router.get("/processes/{process_key}", response_model=ProcessDef)
def get_process_detail(
    process_key: str,
    _: OrgContext = Depends(require_org),
) -> ProcessDef:
    p = get_process(process_key)
    if p is None:
        raise HTTPException(status_code=404, detail=f"unknown process {process_key!r}")
    return _serialize_process(p)


# ── Run lifecycle ────────────────────────────────────────────────────────────


async def _run_in_background(run_id: int) -> None:
    """Open a fresh Session and execute the pipeline. Swallow exceptions —
    the orchestrator already persists `status="failed"` + error message,
    and re-raising would surface as an unhandled task exception in the
    server logs without changing user-visible behavior.
    """
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        try:
            await run_pipeline(db, run_id)
        except Exception:
            pass
    finally:
        db.close()


@router.post("/runs", response_model=StartRunResponse, status_code=status.HTTP_201_CREATED)
async def start_run(
    body: StartRunRequest,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> StartRunResponse:
    kpi = kpi_by_type(body.kpi_type)
    if kpi is None:
        raise HTTPException(status_code=400, detail=f"unknown kpi_type {body.kpi_type!r}")

    run = CacmRun(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        kpi_type=kpi.type,
        process=kpi.process,
        status="running",
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    asyncio.create_task(_run_in_background(run.id))
    return StartRunResponse(run_id=run.id)


@router.get("/runs", response_model=list[RunSummary])
def list_runs(
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> list[RunSummary]:
    rows = (
        db.query(CacmRun)
        .filter(CacmRun.org_id == ctx.org_id)
        .order_by(CacmRun.id.desc())
        .all()
    )
    return [RunSummary.model_validate(r) for r in rows]


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> RunSummary:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    return RunSummary.model_validate(run)


# ── Events ───────────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}/events", response_model=EventsResponse)
def get_events(
    run_id: int,
    since: int = Query(0, ge=0),
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> EventsResponse:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")

    # Lazy stale-run guard — a crashed background task could otherwise leave
    # the UI polling forever. Compare in UTC; older sqlite columns may come
    # back naive, so coerce both sides.
    if run.status == "running":
        started = run.started_at
        if started is not None and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started is not None:
            elapsed = datetime.now(timezone.utc) - started
            if elapsed > _STALE_AFTER:
                run.status = "failed"
                run.error_message = "pipeline did not complete within 5 minutes"
                run.completed_at = datetime.now(timezone.utc)
                db.commit()

    events = (
        db.query(CacmRunEvent)
        .filter(CacmRunEvent.run_id == run_id, CacmRunEvent.seq > since)
        .order_by(CacmRunEvent.seq)
        .all()
    )
    return EventsResponse(
        status=run.status,
        events=[RunEvent.model_validate(e) for e in events],
    )


# ── Exceptions ───────────────────────────────────────────────────────────────


def _gather_exceptions(db: Session, run_id: int, ctx: OrgContext) -> list[CacmException]:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    return (
        db.query(CacmException)
        .filter(CacmException.run_id == run_id)
        .order_by(CacmException.id)
        .all()
    )


@router.get("/runs/{run_id}/exceptions", response_model=ExceptionsResponse)
def list_exceptions(
    run_id: int,
    risk: str | None = Query(None, pattern="^(High|Medium|Low)$"),
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> ExceptionsResponse:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")

    q = db.query(CacmException).filter(CacmException.run_id == run_id)
    if risk:
        q = q.filter(CacmException.risk == risk)
    rows = q.order_by(CacmException.id).all()
    return ExceptionsResponse(
        items=[ExceptionItem.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get("/runs/{run_id}/exceptions.csv")
def export_csv(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> Response:
    rows = _gather_exceptions(db, run_id, ctx)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["exception_no", "risk", "reason", "value", "fields_json", "recommended_action"])
    for r in rows:
        p = r.payload_json or {}
        w.writerow([
            r.exception_no,
            r.risk,
            p.get("reason", ""),
            p.get("value", ""),
            str(p.get("fields", {})),
            p.get("recommended_action", ""),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="cacm_run_{run_id}.csv"'},
    )


@router.get("/runs/{run_id}/exceptions.xlsx")
def export_xlsx(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> Response:
    rows = _gather_exceptions(db, run_id, ctx)
    wb = Workbook()
    ws = wb.active
    ws.title = "Exceptions"
    ws.append(["exception_no", "risk", "reason", "value", "recommended_action"])
    for r in rows:
        p = r.payload_json or {}
        ws.append([
            r.exception_no,
            r.risk,
            p.get("reason", ""),
            p.get("value", ""),
            p.get("recommended_action", ""),
        ])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="cacm_run_{run_id}.xlsx"'},
    )


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/runs/{run_id}/dashboard")
def get_dashboard(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> dict:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")

    excs = (
        db.query(CacmException)
        .filter(CacmException.run_id == run_id)
        .all()
    )

    by_risk: Counter = Counter(e.risk for e in excs)
    by_company: Counter = Counter()
    by_vendor: Counter = Counter()
    monthly: Counter = Counter()
    for e in excs:
        fields = (e.payload_json or {}).get("fields", {}) or {}
        if fields.get("company_code"):
            by_company[str(fields["company_code"])] += 1
        if fields.get("vendor_code"):
            by_vendor[str(fields["vendor_code"])] += 1
        # First date-like field in the payload determines the monthly bucket.
        for k, v in fields.items():
            if "date" in k.lower() and isinstance(v, str) and len(v) >= 7:
                monthly[v[:7]] += 1
                break

    return {
        "totals": {
            "records": run.total_records or 0,
            "exceptions": run.total_exceptions or 0,
            "exception_pct": run.exception_pct or 0.0,
        },
        "by_risk": dict(by_risk),
        "by_company": dict(by_company.most_common(10)),
        "by_vendor": dict(by_vendor.most_common(10)),
        "monthly_trend": dict(sorted(monthly.items())),
    }


# ── Wizard stage detail endpoints ────────────────────────────────────────────
#
# Synthesize per-stage details on demand from the sample-data JSON. The
# pipeline already ran via POST /runs; these endpoints just re-load the
# relevant tables and return a richer view for the UI to reveal at the
# user's pace.

# Hardcoded transformations and target-load tables per process. Keep these
# in sync with what the orchestrator actually does inside `run_pipeline` —
# they're descriptive labels, not authoritative state.
_TRANSFORMATION_RULES: dict[str, list[str]] = {
    "Procurement": [
        "Convert all date fields into a consistent system date format, including PO Creation Date, Vendor Invoice Date, GR/IR Posting Date, and GR/IR Entry Date.",
        "Trim leading and trailing spaces from all text-based fields to ensure consistent matching and reporting.",
        "Handle blank, null, and special-character values across mandatory fields to improve data quality.",
        "Normalize amount and quantity fields into numeric format for reporting and aggregation.",
        "Standardize key fields such as Company Code, Plant, PO Number, PO Line Item, Document Type, User ID, Quantity, and Amount fields.",
    ],
    "Inventory": [
        "Convert all date fields into a consistent system date format, including Posting Date and Document Date.",
        "Trim leading and trailing spaces from all text-based fields to ensure consistent matching and reporting.",
        "Handle blank, null, and special-character values across mandatory fields to improve data quality.",
        "Normalize quantity and amount fields into numeric format for reporting and aggregation.",
        "Standardize key fields such as Material ID, Movement Type, Plant, User ID, and Quantity fields.",
    ],
}


_LOAD_TARGET_TABLES: dict[str, list[str]] = {
    "Procurement": [
        "ccm_po_header",
        "ccm_po_line_items",
        "ccm_vendor_master",
        "ccm_invoice_header",
        "ccm_invoice_line_items",
        "ccm_rule_execution_log",
    ],
    "Inventory": [
        "ccm_material_master",
        "ccm_inventory_movements",
        "ccm_rule_execution_log",
    ],
}


def _coerce_for_json(value):
    """Make a sample-row cell JSON-friendly. Mirrors `_json_safe` from the
    rule pattern but kept local so this module doesn't reach into
    `rule_patterns` for a private helper."""
    import math

    import pandas as pd

    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if hasattr(value, "item") and not isinstance(value, str):
        try:
            value = value.item()
        except (ValueError, TypeError):
            pass
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def _load_run_tables(run: CacmRun):
    """Re-load sample tables for the run's process, mirroring the orchestrator's
    extract+transform stages. Returns the (raw, derived) split so the wizard
    can talk about them separately.
    """
    import json
    from pathlib import Path

    import pandas as pd

    if run.process not in _PROCESS_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"no sample data registered for process {run.process!r}",
        )
    path: Path = SAMPLE_DATA_DIR / _PROCESS_FILES[run.process]
    raw_json = json.loads(path.read_text())
    tables = {name: pd.DataFrame(rows) for name, rows in raw_json.items()}
    # Apply the same string cleanup + date parsing the orchestrator runs so
    # downstream callers see typed columns.
    for df in tables.values():
        for c in df.select_dtypes(include="object").columns:
            df[c] = df[c].fillna("").astype(str).str.strip()
    _date_columns(tables)
    derived = _build_derived_tables(run.process, tables)
    return tables, derived


def _resolve_run(db: Session, run_id: int, ctx: OrgContext) -> CacmRun:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get(
    "/runs/{run_id}/stage/extraction",
    response_model=ExtractionStageResponse,
)
def stage_extraction(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> ExtractionStageResponse:
    run = _resolve_run(db, run_id, ctx)
    kpi = kpi_by_type(run.kpi_type)
    if kpi is None:
        raise HTTPException(status_code=400, detail=f"unknown kpi_type {run.kpi_type!r}")

    tables, _ = _load_run_tables(run)

    extracted: list[ExtractedTable] = []
    for name, df in tables.items():
        sample = df.head(10).to_dict(orient="records")
        sample = [
            {k: _coerce_for_json(v) for k, v in row.items()}
            for row in sample
        ]
        extracted.append(ExtractedTable(
            name=name,
            row_count=int(len(df)),
            columns=list(df.columns),
            sample_rows=sample,
            download_url=(
                f"/api/cacm/runs/{run_id}/stage/extraction/download/{name}.csv"
            ),
        ))

    return ExtractionStageResponse(
        source_system="SAP ECC (sample)",
        planned_tables=list(kpi.source_tables),
        tables=extracted,
        extracted_at=run.started_at or datetime.now(timezone.utc),
    )


@router.get(
    "/runs/{run_id}/stage/transformation",
    response_model=TransformationStageResponse,
)
def stage_transformation(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> TransformationStageResponse:
    run = _resolve_run(db, run_id, ctx)
    tables, derived = _load_run_tables(run)

    rows_in = sum(int(len(t)) for t in tables.values())
    rows_out = sum(int(len(t)) for t in derived.values()) if derived else rows_in

    derived_summaries: list[DerivedTableSummary] = []
    if run.process == "Procurement":
        for name, df in derived.items():
            derived_summaries.append(DerivedTableSummary(
                name=name,
                source_join_summary=(
                    "INNER JOIN ekko (PO) ⟷ rbkp (Invoice) ON ekko.po_no = rbkp.po_ref"
                ),
                row_count=int(len(df)),
            ))
    elif run.process == "Inventory":
        for name, df in derived.items():
            derived_summaries.append(DerivedTableSummary(
                name=name,
                source_join_summary=(
                    "FILTER mseg WHERE movement_type IN (309, 561, 562, 701, 702)"
                ),
                row_count=int(len(df)),
            ))
    else:
        for name, df in derived.items():
            derived_summaries.append(DerivedTableSummary(
                name=name, source_join_summary="(derived)", row_count=int(len(df)),
            ))

    return TransformationStageResponse(
        rules_applied=_TRANSFORMATION_RULES.get(run.process, []),
        rows_in=rows_in,
        rows_out=rows_out,
        derived_tables=derived_summaries,
    )


@router.get(
    "/runs/{run_id}/stage/loading",
    response_model=LoadingStageResponse,
)
def stage_loading(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> LoadingStageResponse:
    run = _resolve_run(db, run_id, ctx)
    targets = _LOAD_TARGET_TABLES.get(run.process, ["ccm_rule_execution_log"])
    tables, _ = _load_run_tables(run)
    # Approximate row counts: distribute the source-table totals across the
    # CCM mart targets in a way that's plausible for the demo. Rule log
    # always equals the total exceptions.
    total_rows = sum(int(len(t)) for t in tables.values())
    log_rows = run.total_exceptions or 0
    other_targets = [t for t in targets if t != "ccm_rule_execution_log"]
    per_target = total_rows // max(len(other_targets), 1) if other_targets else 0

    loaded: list[LoadedTable] = []
    for t in targets:
        if t == "ccm_rule_execution_log":
            loaded.append(LoadedTable(name=t, row_count=int(log_rows), status="loaded"))
        else:
            loaded.append(LoadedTable(name=t, row_count=int(per_target), status="loaded"))
    return LoadingStageResponse(target_tables=loaded)


@router.get(
    "/runs/{run_id}/stage/rule-engine",
    response_model=RuleEngineStageResponse,
)
def stage_rule_engine(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> RuleEngineStageResponse:
    run = _resolve_run(db, run_id, ctx)
    kpi = kpi_by_type(run.kpi_type)
    if kpi is None:
        raise HTTPException(status_code=400, detail=f"unknown kpi_type {run.kpi_type!r}")
    tables, _ = _load_run_tables(run)
    total_evaluated = sum(int(len(t)) for t in tables.values())
    return RuleEngineStageResponse(
        kpi_type=kpi.type,
        kpi_name=kpi.name,
        pattern=kpi.pattern,
        source_tables=list(kpi.source_tables),
        conditions=list(kpi.rule_conditions),
        rule_summary=kpi.rule_objective,
        exceptions_generated=int(run.total_exceptions or 0),
        total_evaluated=total_evaluated,
    )


@router.get("/runs/{run_id}/stage/extraction/download/{table_name}.csv")
def stage_extraction_download(
    run_id: int,
    table_name: str,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> Response:
    run = _resolve_run(db, run_id, ctx)
    # Defensive — table_name is shoved into a filename, so reject anything
    # that's not a plain identifier.
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="invalid table name")
    tables, _ = _load_run_tables(run)
    if table_name not in tables:
        raise HTTPException(status_code=404, detail=f"unknown table {table_name!r}")

    df = tables[table_name]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(list(df.columns))
    for _, row in df.iterrows():
        w.writerow([_coerce_for_json(row[c]) for c in df.columns])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition":
                f'attachment; filename="cacm_run_{run_id}_{table_name}.csv"',
        },
    )
