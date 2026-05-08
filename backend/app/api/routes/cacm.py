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
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.agents.cacm.kpi_catalog import kpi_by_type, kpis_by_process
from app.agents.cacm.process_catalog import get_process, get_processes
from app.agents.cacm.schedule_math import compute_next_run_at
from app.agents.cacm.service import (
    SAMPLE_DATA_DIR,
    _PROCESS_FILES,
    _build_derived_tables,
    _date_columns,
    run_pipeline,
)
from app.api.deps import OrgContext, get_db, require_org
from app.models.cacm import CacmException, CacmRun, CacmRunEvent, CacmSchedule
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
    ScheduleCreate,
    ScheduleSummary,
    ScheduleUpdate,
    SchedulesResponse,
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


# ── Schedules ────────────────────────────────────────────────────────────────


def _resolve_kri(process_key: str, kri_name: str) -> str:
    """Look up `kpi_type` for a (process, kri_name) pair, or raise 400."""
    proc = get_process(process_key)
    if proc is None:
        raise HTTPException(
            status_code=400, detail=f"unknown process {process_key!r}",
        )
    for kri in proc.kris:
        if kri.name == kri_name:
            return kri.kpi_type
    raise HTTPException(
        status_code=400,
        detail=f"unknown kri {kri_name!r} in process {process_key!r}",
    )


@router.post(
    "/schedules",
    response_model=ScheduleSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    body: ScheduleCreate,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> ScheduleSummary:
    kpi_type = _resolve_kri(body.process_key, body.kri_name)
    now = datetime.now(timezone.utc)
    next_run = compute_next_run_at(body.frequency, body.time_of_day, now=now)

    existing = (
        db.query(CacmSchedule)
        .filter(
            CacmSchedule.org_id == ctx.org_id,
            CacmSchedule.process_key == body.process_key,
            CacmSchedule.kri_name == body.kri_name,
        )
        .one_or_none()
    )
    if existing is not None:
        existing.frequency = body.frequency
        existing.time_of_day = body.time_of_day
        existing.kpi_type = kpi_type
        existing.next_run_at = next_run
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return ScheduleSummary.model_validate(existing)

    row = CacmSchedule(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        process_key=body.process_key,
        kri_name=body.kri_name,
        kpi_type=kpi_type,
        frequency=body.frequency,
        time_of_day=body.time_of_day,
        next_run_at=next_run,
        is_active=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return ScheduleSummary.model_validate(row)


@router.get("/schedules", response_model=SchedulesResponse)
def list_schedules(
    process_key: str | None = Query(None),
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> SchedulesResponse:
    q = db.query(CacmSchedule).filter(CacmSchedule.org_id == ctx.org_id)
    if process_key:
        q = q.filter(CacmSchedule.process_key == process_key)
    rows = q.order_by(CacmSchedule.id).all()
    return SchedulesResponse(
        schedules=[ScheduleSummary.model_validate(r) for r in rows],
    )


@router.put("/schedules/{schedule_id}", response_model=ScheduleSummary)
def update_schedule(
    schedule_id: int,
    body: ScheduleUpdate,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> ScheduleSummary:
    row = db.get(CacmSchedule, schedule_id)
    if row is None or row.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="schedule not found")
    row.frequency = body.frequency
    row.time_of_day = body.time_of_day
    row.next_run_at = compute_next_run_at(
        body.frequency, body.time_of_day, now=datetime.now(timezone.utc),
    )
    db.commit()
    db.refresh(row)
    return ScheduleSummary.model_validate(row)


@router.delete("/schedules/{schedule_id}")
def delete_schedule(
    schedule_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> dict:
    row = db.get(CacmSchedule, schedule_id)
    if row is None or row.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="schedule not found")
    db.delete(row)
    db.commit()
    return {"deleted": True}


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


# Aging-bucket thresholds — mirror `_aging_bucket` in service.py but keep
# both labels (audit-friendly + dashboard "0-3 Days") and the risk level.
_AGING_BUCKETS = (
    ("0-3 Days", "Low", 0, 3),
    ("4-14 Days", "Medium", 4, 14),
    ("15+ Days", "High", 15, 10**9),
)

# Month order for the monthly trend (Apr → Mar fiscal-year style).
_MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# Distinct colours for the location grid, recycled if more than 5 locations.
_LOCATION_COLOURS = ["purple", "red", "blue", "orange", "green"]

# Pretty-label company codes — shown next to the raw code in the breakdown.
_COMPANY_LABELS = {"1000": "Acme", "2000": "Beta", "3000": "Gamma"}


# ── Inventory dashboard support ──────────────────────────────────────────────

# Inventory company labels — match the user's mockup (ACME / Vertex / Nexus / Apex).
_INV_COMPANY_LABELS = {
    "1000": "ACME",
    "2000": "Vertex",
    "3000": "Nexus",
    "4000": "Apex",
}

# Plant labels — pretty city names attached to the SAP plant code.
_INV_LOCATION_LABELS = {
    "BLR1": "Bengaluru",
    "CHN1": "Chennai",
    "MUM1": "Mumbai",
    "HYD1": "Hyderabad",
    "DEL1": "Delhi",
}

# Per-location colour token, keyed by werks. Recharts/CSS resolves these
# tokens via LOCATION_COLOR_MAP on the frontend.
_INV_LOCATION_COLOURS = {
    "BLR1": "purple",
    "CHN1": "red",
    "MUM1": "orange",
    "HYD1": "teal",
    "DEL1": "green",
}

# Movement type catalog — keep a stable order so the bar chart axis doesn't
# shuffle as filters change. Each entry: (code, label, color-token).
_INV_MOVEMENT_TYPES: list[tuple[str, str, str]] = [
    ("701", "701 Surplus", "orange"),
    ("702", "702 Deficit", "red"),
    ("551", "551 Scrap", "purple"),
    ("561", "561 Init.Stock", "teal"),
    ("562", "562 Rev.Init", "lavender"),
    ("552", "552 Rev.Scrap", "amber"),
    ("711", "711 Blocked", "green"),
    ("712", "712 Rev.Blk", "grey"),
]

# Material-group → colour mapping for the donut chart.
_INV_MATERIAL_GROUP_COLOURS = {
    "Electronics": "purple",
    "Mechanical": "red",
    "Raw Material": "orange",
    "Lubricants": "teal",
    "Packaging": "amber",
    "Safety": "green",
}


def _inv_risk_from_count(count: float | int | None) -> str:
    """Derive risk band from adjustment count, mirroring the kpi_catalog
    risk bands [(4,5,Low),(6,9,Medium),(10,None,High)]."""
    try:
        c = int(count or 0)
    except (TypeError, ValueError):
        c = 0
    if c >= 10:
        return "High"
    if c >= 6:
        return "Medium"
    return "Low"


def _inventory_exception_view(e: CacmException) -> dict:
    """Flatten an inventory exception into a denormalised dict for filter/aggregation.

    Falls back gracefully if any field is missing — the orchestrator
    populates them via `metadata_fields` on the kpi_catalog spec, but
    older runs may not.
    """
    payload = e.payload_json or {}
    fields = payload.get("fields") or {}
    agg_value = fields.get("agg_value") or 0
    return {
        "exception_no": e.exception_no,
        "risk": e.risk or _inv_risk_from_count(agg_value),
        "agg_value": int(float(agg_value)) if agg_value else 0,
        "company_code": str(fields.get("company_code") or "") or None,
        "werks": str(fields.get("werks") or "") or None,
        "lgort": str(fields.get("lgort") or "") or None,
        "material_id": fields.get("material_id") or None,
        "material_name": fields.get("material_name") or None,
        "material_group": fields.get("material_group") or None,
        "movement_type": str(fields.get("movement_type") or "") or None,
        "posting_date": fields.get("posting_date") or None,
        "adjustment_amount": float(fields.get("adjustment_amount") or 0),
        "user_id": fields.get("user_id") or None,
        "reversal_indicator": bool(fields.get("reversal_indicator") or False),
    }


def _build_inventory_dashboard(run: CacmRun, excs: list[CacmException], q: dict) -> dict:
    """Compute the Inventory-shape dashboard payload.

    `q` is a dict of CSV-string filter params (companies, locations,
    risk_levels, movement_types, material_groups, reversals). Filters
    narrow the exception set BEFORE every aggregation except
    `filter_options`, which always returns the full distinct set.
    """
    all_views = [_inventory_exception_view(e) for e in excs]

    filter_options = {
        "companies": sorted({v["company_code"] for v in all_views if v["company_code"]}),
        "locations": sorted({v["werks"] for v in all_views if v["werks"]}),
        "risk_levels": ["High", "Medium", "Low"],
        "movement_types": sorted({v["movement_type"] for v in all_views if v["movement_type"]}),
        "material_groups": sorted({v["material_group"] for v in all_views if v["material_group"]}),
        "reversals": ["Yes", "No"],
    }

    f_companies = set(_split_csv(q.get("companies")))
    f_locations = set(_split_csv(q.get("locations")))
    f_risks = set(_split_csv(q.get("risk_levels")))
    f_movement_types = set(_split_csv(q.get("movement_types")))
    f_material_groups = set(_split_csv(q.get("material_groups")))
    # Reversals filter is Yes / No / both.
    f_reversals_raw = _split_csv(q.get("reversals"))
    f_reversals: set[bool] = set()
    for v in f_reversals_raw:
        if v.lower() == "yes":
            f_reversals.add(True)
        elif v.lower() == "no":
            f_reversals.add(False)

    def _passes(v: dict) -> bool:
        if f_companies and (v["company_code"] not in f_companies):
            return False
        if f_locations and (v["werks"] not in f_locations):
            return False
        if f_risks and (v["risk"] not in f_risks):
            return False
        if f_movement_types and (v["movement_type"] not in f_movement_types):
            return False
        if f_material_groups and (v["material_group"] not in f_material_groups):
            return False
        if f_reversals and (v["reversal_indicator"] not in f_reversals):
            return False
        return True

    views = [v for v in all_views if _passes(v)]
    total_exceptions = len(views)

    # ── Totals tiles ────────────────────────────────────────────────────────
    # Spec says "High Risk (>= 6 ADJ.)" — the dashboard tile counts every
    # exception whose adjustment count crosses 6, which spans both the
    # Medium risk band (6-9) and the High band (10+).
    high_risk_count = sum(1 for v in views if v["agg_value"] >= 6)
    high_risk_pct = (high_risk_count / total_exceptions * 100.0) if total_exceptions else 0.0
    total_adj_value = sum(abs(v["adjustment_amount"]) for v in views)
    avg_adj_count = (sum(v["agg_value"] for v in views) / total_exceptions) if total_exceptions else 0.0
    reversal_count = sum(1 for v in views if v["reversal_indicator"])
    reversal_pct = (reversal_count / total_exceptions * 100.0) if total_exceptions else 0.0
    unique_materials = len({v["material_id"] for v in views if v["material_id"]})

    totals = {
        "total_exceptions": total_exceptions,
        "high_risk_count": high_risk_count,
        "high_risk_pct": round(high_risk_pct, 1),
        "total_adj_value": round(total_adj_value, 2),
        "avg_adj_count": round(avg_adj_count, 1),
        "reversal_transactions": reversal_count,
        "reversal_pct": round(reversal_pct, 1),
        "unique_materials": unique_materials,
        # Legacy keys some clients still consume.
        "records": run.total_records or 0,
        "exceptions": total_exceptions,
        "exception_pct": run.exception_pct or 0.0,
        "total_records": run.total_records or 0,
    }

    # ── Movement type distribution (vertical bar) ───────────────────────────
    # Always show all 8 spec types in stable order; missing ones get 0.
    counts_by_mt: dict[str, int] = {}
    for v in views:
        mt = v["movement_type"]
        if not mt:
            continue
        counts_by_mt[mt] = counts_by_mt.get(mt, 0) + 1
    movement_type_distribution = [
        {"code": code, "label": label, "color": colour, "count": int(counts_by_mt.get(code, 0))}
        for code, label, colour in _INV_MOVEMENT_TYPES
    ]

    # ── Monthly trend (Apr-Dec area + line) ─────────────────────────────────
    monthly_map: dict[str, dict[str, float]] = {}
    for v in views:
        d = v["posting_date"]
        if not d or len(d) < 7:
            continue
        ym = d[:7]
        bucket = monthly_map.setdefault(ym, {"count": 0, "total_value": 0.0})
        bucket["count"] += 1
        bucket["total_value"] += abs(v["adjustment_amount"])

    monthly_trend = []
    for ym in sorted(monthly_map.keys()):
        try:
            month_idx = int(ym[5:7])
            month_label = _MONTH_ABBR[month_idx - 1]
        except (ValueError, IndexError):
            month_label = ym
        monthly_trend.append({
            "month": month_label,
            "year_month": ym,
            "exceptions": int(monthly_map[ym]["count"]),
            "total_value": round(monthly_map[ym]["total_value"], 2),
        })

    # ── Company breakdown — stacked bars by risk ────────────────────────────
    company_bucket: dict[str, dict[str, int]] = {}
    for v in views:
        cc = v["company_code"]
        if not cc:
            continue
        b = company_bucket.setdefault(cc, {"high": 0, "medium": 0, "low": 0})
        b[v["risk"].lower()] = b.get(v["risk"].lower(), 0) + 1
    company_breakdown = []
    for cc in sorted(company_bucket.keys()):
        b = company_bucket[cc]
        label_name = _INV_COMPANY_LABELS.get(cc, cc)
        company_breakdown.append({
            "company_code": cc,
            "label": f"{label_name} ({cc})",
            "high": int(b.get("high", 0)),
            "medium": int(b.get("medium", 0)),
            "low": int(b.get("low", 0)),
            "count": int(b.get("high", 0) + b.get("medium", 0) + b.get("low", 0)),
        })

    # ── Material group exposure — donut ─────────────────────────────────────
    group_bucket: dict[str, float] = {}
    for v in views:
        g = v["material_group"]
        if not g:
            continue
        group_bucket[g] = group_bucket.get(g, 0.0) + abs(v["adjustment_amount"])
    total_group_value = sum(group_bucket.values()) or 1.0
    material_group_exposure = []
    for g, val in sorted(group_bucket.items(), key=lambda kv: -kv[1]):
        material_group_exposure.append({
            "group": g,
            "value": round(val, 2),
            "pct": round(val / total_group_value * 100.0, 1),
            "color": _INV_MATERIAL_GROUP_COLOURS.get(g, "purple"),
        })

    # ── Location analysis — horizontal bars ─────────────────────────────────
    loc_bucket: dict[str, dict[str, int]] = {}
    for v in views:
        loc = v["werks"]
        if not loc:
            continue
        b = loc_bucket.setdefault(loc, {"count": 0, "high_count": 0})
        b["count"] += 1
        if v["risk"] == "High":
            b["high_count"] += 1
    location_analysis = []
    for loc in sorted(loc_bucket.keys(), key=lambda k: -loc_bucket[k]["count"]):
        b = loc_bucket[loc]
        label_name = _INV_LOCATION_LABELS.get(loc, loc)
        location_analysis.append({
            "location": loc,
            "label": f"{label_name} ({loc})",
            "count": int(b["count"]),
            "high_count": int(b["high_count"]),
            "color": _INV_LOCATION_COLOURS.get(loc, "purple"),
        })

    # Legacy keys for backwards-compat / existing /test_cacm_dashboard expectations.
    by_risk = {"High": 0, "Medium": 0, "Low": 0}
    for v in views:
        by_risk[v["risk"]] = by_risk.get(v["risk"], 0) + 1
    by_risk = {k: c for k, c in by_risk.items() if c > 0}
    by_company_legacy = {row["company_code"]: row["count"] for row in company_breakdown[:10]}

    return {
        "kpi_type": run.kpi_type,
        "process": run.process,
        "totals": totals,
        "filter_options": filter_options,
        "movement_type_distribution": movement_type_distribution,
        "monthly_trend": monthly_trend,
        "company_breakdown": company_breakdown,
        "material_group_exposure": material_group_exposure,
        "location_analysis": location_analysis,
        # Legacy keys still consumed by older smoke tests / generic dashboard.
        "by_risk": by_risk,
        "by_company": by_company_legacy,
        "by_vendor": {},
    }


def _aging_for(diff_days: float | int | None) -> tuple[str, str]:
    """Return (bucket_label, risk_level) for a delay in days. Defaults to Low/0-3."""
    try:
        d = int(diff_days) if diff_days is not None else 0
    except (TypeError, ValueError):
        d = 0
    for label, risk, lo, hi in _AGING_BUCKETS:
        if lo <= d <= hi:
            return label, risk
    return _AGING_BUCKETS[-1][0], _AGING_BUCKETS[-1][1]


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _exception_view(e: CacmException) -> dict:
    """Flatten an exception into a denormalised dict for filter/aggregation."""
    payload = e.payload_json or {}
    fields = payload.get("fields") or {}
    diff_days = fields.get("diff_days") or 0
    aging_label, aging_risk = _aging_for(diff_days)
    return {
        "exception_no": e.exception_no,
        "risk": e.risk,
        "diff_days": int(diff_days) if isinstance(diff_days, (int, float)) else 0,
        "company_code": str(fields.get("company_code") or "") or None,
        "location": fields.get("location") or None,
        "po_created_by": fields.get("po_created_by") or None,
        "invoice_amount": float(fields.get("invoice_amount") or 0),
        "po_amount": float(fields.get("po_amount") or 0),
        "po_created": fields.get("po_created") or None,
        "invoice_posted": fields.get("invoice_posted") or None,
        "aging_label": aging_label,
        "aging_risk": aging_risk,
    }


@router.get("/runs/{run_id}/dashboard")
def get_dashboard(
    run_id: int,
    companies: str | None = Query(None),
    locations: str | None = Query(None),
    risk_levels: str | None = Query(None),
    aging_buckets: str | None = Query(None),
    po_creators: str | None = Query(None),
    movement_types: str | None = Query(None),
    material_groups: str | None = Query(None),
    reversals: str | None = Query(None),
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

    # ── Inventory KPI: branch to the inventory-specific payload ─────────────
    if run.kpi_type == "repeated_material_adjustments" or run.process == "Inventory":
        return _build_inventory_dashboard(
            run,
            excs,
            {
                "companies": companies,
                "locations": locations,
                "risk_levels": risk_levels,
                "movement_types": movement_types,
                "material_groups": material_groups,
                "reversals": reversals,
            },
        )

    # All exceptions (denormalised) — used for filter_options (always full set).
    all_views = [_exception_view(e) for e in excs]

    # Filter options — derived from the full unfiltered view so dropdowns
    # don't shrink as filters apply.
    company_set = sorted({v["company_code"] for v in all_views if v["company_code"]})
    location_set = sorted({v["location"] for v in all_views if v["location"]})
    creator_set = sorted({v["po_created_by"] for v in all_views if v["po_created_by"]})
    filter_options = {
        "companies": company_set,
        "locations": location_set,
        "risk_levels": ["High", "Medium", "Low"],
        "aging_buckets": [b[0] for b in _AGING_BUCKETS],
        "po_creators": creator_set,
    }

    # Apply filters.
    f_companies = set(_split_csv(companies))
    f_locations = set(_split_csv(locations))
    f_risks = set(_split_csv(risk_levels))
    f_aging = set(_split_csv(aging_buckets))
    f_creators = set(_split_csv(po_creators))

    def _passes(v: dict) -> bool:
        if f_companies and (v["company_code"] not in f_companies):
            return False
        if f_locations and (v["location"] not in f_locations):
            return False
        if f_risks and (v["risk"] not in f_risks):
            return False
        if f_aging and (v["aging_label"] not in f_aging):
            return False
        if f_creators and (v["po_created_by"] not in f_creators):
            return False
        return True

    views = [v for v in all_views if _passes(v)]
    total_exceptions = len(views)

    # Totals
    high_risk_count = sum(1 for v in views if v["risk"] == "High")
    high_risk_pct = (high_risk_count / total_exceptions * 100.0) if total_exceptions else 0.0
    total_invoice_amt = sum(v["invoice_amount"] for v in views)
    avg_delay_days = (sum(v["diff_days"] for v in views) / total_exceptions) if total_exceptions else 0.0
    if views:
        max_v = max(views, key=lambda v: v["diff_days"])
        max_delay_days = int(max_v["diff_days"])
        max_delay_location = max_v["location"] or ""
    else:
        max_delay_days = 0
        max_delay_location = ""

    # Monthly trend (uses po_created month; sort calendar order).
    monthly_map: dict[str, dict[str, float]] = {}
    for v in views:
        d = v["po_created"]
        if not d or len(d) < 7:
            continue
        ym = d[:7]
        bucket = monthly_map.setdefault(ym, {"count": 0, "delay_sum": 0.0})
        bucket["count"] += 1
        bucket["delay_sum"] += v["diff_days"]
    monthly_trend = []
    for ym in sorted(monthly_map.keys()):
        cnt = int(monthly_map[ym]["count"])
        avg = (monthly_map[ym]["delay_sum"] / cnt) if cnt else 0.0
        try:
            month_idx = int(ym[5:7])
            month_label = _MONTH_ABBR[month_idx - 1]
        except (ValueError, IndexError):
            month_label = ym
        monthly_trend.append(
            {"month": month_label, "year_month": ym, "exceptions": cnt, "avg_delay": round(avg, 2)}
        )

    # Company breakdown — count + invoice_amt + per-risk segments.
    company_buckets: dict[str, dict[str, Any]] = {}
    for v in views:
        cc = v["company_code"]
        if not cc:
            continue
        b = company_buckets.setdefault(cc, {"count": 0, "total_invoice_amt": 0.0,
                                            "high": 0, "medium": 0, "low": 0})
        b["count"] += 1
        b["total_invoice_amt"] += v["invoice_amount"]
        if v["risk"] == "High":
            b["high"] += 1
        elif v["risk"] == "Medium":
            b["medium"] += 1
        else:
            b["low"] += 1
    company_breakdown = []
    for cc, b in sorted(company_buckets.items(), key=lambda kv: -kv[1]["count"]):
        label_name = _COMPANY_LABELS.get(cc, cc)
        company_breakdown.append({
            "company_code": cc,
            "label": f"{label_name} ({cc})",
            "count": b["count"],
            "total_invoice_amt": b["total_invoice_amt"],
            "high": b["high"],
            "medium": b["medium"],
            "low": b["low"],
        })

    # Aging buckets — always 3 entries, even if some are 0.
    aging_counts: dict[str, int] = {b[0]: 0 for b in _AGING_BUCKETS}
    for v in views:
        aging_counts[v["aging_label"]] += 1
    aging_buckets_out = []
    for label, risk, _lo, _hi in _AGING_BUCKETS:
        cnt = aging_counts[label]
        pct = (cnt / total_exceptions * 100.0) if total_exceptions else 0.0
        aging_buckets_out.append({
            "label": label, "risk": risk, "count": cnt, "pct": round(pct, 1),
        })

    # PO creators — top 10 by count.
    creator_buckets: dict[str, dict[str, float]] = {}
    for v in views:
        u = v["po_created_by"]
        if not u:
            continue
        b = creator_buckets.setdefault(u, {"count": 0, "total_invoice_amt": 0.0})
        b["count"] += 1
        b["total_invoice_amt"] += v["invoice_amount"]
    po_creators_out = []
    for user, b in sorted(creator_buckets.items(), key=lambda kv: (-kv[1]["count"], kv[0]))[:10]:
        po_creators_out.append({
            "user": user,
            "count": int(b["count"]),
            "total_invoice_amt": b["total_invoice_amt"],
        })

    # Financial exposure — every (filtered) exception with the bubble dims.
    financial_exposure = [
        {
            "exception_no": v["exception_no"],
            "delay_days": v["diff_days"],
            "invoice_amount": v["invoice_amount"],
            "po_amount": v["po_amount"],
            "risk": v["risk"],
        }
        for v in views
    ]

    # Location breakdown — count, ₹ exposure, % of filtered total.
    location_buckets: dict[str, dict[str, float]] = {}
    for v in views:
        loc = v["location"]
        if not loc:
            continue
        b = location_buckets.setdefault(loc, {"count": 0, "total_invoice_amt": 0.0})
        b["count"] += 1
        b["total_invoice_amt"] += v["invoice_amount"]
    location_breakdown = []
    for idx, (loc, b) in enumerate(sorted(location_buckets.items(), key=lambda kv: -kv[1]["count"])):
        pct = (b["count"] / total_exceptions * 100.0) if total_exceptions else 0.0
        location_breakdown.append({
            "location": loc,
            "count": int(b["count"]),
            "total_invoice_amt": b["total_invoice_amt"],
            "pct_of_total": round(pct, 1),
            "color": _LOCATION_COLOURS[idx % len(_LOCATION_COLOURS)],
        })

    # ── Backward-compat keys (legacy test + Inventory dashboard) ────────────
    by_risk = {"High": 0, "Medium": 0, "Low": 0}
    for v in views:
        by_risk[v["risk"]] = by_risk.get(v["risk"], 0) + 1
    by_risk = {k: c for k, c in by_risk.items() if c > 0}
    by_company_legacy = {row["company_code"]: row["count"] for row in company_breakdown[:10]}
    by_vendor: Counter = Counter()
    for e in excs:
        fields = (e.payload_json or {}).get("fields", {}) or {}
        if fields.get("vendor_code"):
            by_vendor[str(fields["vendor_code"])] += 1

    return {
        "totals": {
            # Legacy keys the original dashboard test asserts on.
            "records": run.total_records or 0,
            "exceptions": total_exceptions,
            "exception_pct": run.exception_pct or 0.0,
            # New, richer totals.
            "total_exceptions": total_exceptions,
            "total_records": run.total_records or 0,
            "high_risk_count": high_risk_count,
            "high_risk_pct": round(high_risk_pct, 1),
            "total_invoice_amt": total_invoice_amt,
            "avg_delay_days": round(avg_delay_days, 1),
            "max_delay_days": max_delay_days,
            "max_delay_location": max_delay_location,
        },
        "filter_options": filter_options,
        "monthly_trend": monthly_trend,
        "company_breakdown": company_breakdown,
        "aging_buckets": aging_buckets_out,
        "po_creators": po_creators_out,
        "financial_exposure": financial_exposure,
        "location_breakdown": location_breakdown,
        # Legacy keys for the original test + Inventory dashboard.
        "by_risk": by_risk,
        "by_company": by_company_legacy,
        "by_vendor": dict(by_vendor.most_common(10)),
        "kpi_type": run.kpi_type,
        "process": run.process,
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
                    "FILTER mseg WHERE movement_type IN "
                    "(551, 552, 561, 562, 701, 702, 711, 712)"
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
