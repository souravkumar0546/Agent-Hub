"""Pydantic request/response schemas for the CACM API.

Kept colocated with the route module — every shape here is referenced
only by `app.api.routes.cacm`, so a single file avoids the schema-sprawl
problem.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Library ──────────────────────────────────────────────────────────────────


class KpiSummary(BaseModel):
    type: str
    name: str
    description: str
    rule_objective: str
    pattern: str
    source_tables: list[str]


class ProcessGroup(BaseModel):
    name: str
    kpis: list[KpiSummary]


class LibraryResponse(BaseModel):
    processes: list[ProcessGroup]


# ── Process catalog (Process Picker screen) ──────────────────────────────────


class KriSummary(BaseModel):
    name: str
    kpi_type: str | None = None


class ProcessDef(BaseModel):
    key: str
    name: str
    intro: str
    kris: list[KriSummary]


class ProcessesResponse(BaseModel):
    processes: list[ProcessDef]


# ── Run lifecycle ────────────────────────────────────────────────────────────


class StartRunRequest(BaseModel):
    kpi_type: str = Field(min_length=1, max_length=80)


class StartRunResponse(BaseModel):
    run_id: int


class RunSummary(BaseModel):
    id: int
    kpi_type: str
    process: str
    status: str
    started_at: datetime
    completed_at: datetime | None
    total_records: int | None
    total_exceptions: int | None
    exception_pct: float | None
    summary_json: dict[str, Any] | None
    error_message: str | None

    model_config = {"from_attributes": True}


# ── Events polling ───────────────────────────────────────────────────────────


class RunEvent(BaseModel):
    seq: int
    stage: str
    message: str
    payload_json: dict[str, Any] | None
    ts: datetime

    model_config = {"from_attributes": True}


class EventsResponse(BaseModel):
    status: str
    events: list[RunEvent]


# ── Exceptions ───────────────────────────────────────────────────────────────


class ExceptionItem(BaseModel):
    id: int
    exception_no: str
    risk: str
    payload_json: dict[str, Any]

    model_config = {"from_attributes": True}


class ExceptionsResponse(BaseModel):
    items: list[ExceptionItem]
    total: int


# ── Stage-detail responses (wizard) ──────────────────────────────────────────
#
# Five GET endpoints that surface what happens at each pipeline stage so the
# step-by-step wizard can render plausible "this is what's about to run" /
# "this is what just ran" details. Data is recomputed from the sample-data
# JSON on each request (no intermediate persistence) — that's fine because
# the demo dataset is tiny.


class ExtractedTable(BaseModel):
    name: str                                  # table name e.g. "ekko"
    row_count: int
    columns: list[str]
    sample_rows: list[dict[str, Any]]          # head(10), JSON-coerced
    download_url: str                          # CSV download endpoint


class ExtractionStageResponse(BaseModel):
    source_system: str
    planned_tables: list[str]                  # names from KpiDef.source_tables
    tables: list[ExtractedTable]
    extracted_at: datetime


class DerivedTableSummary(BaseModel):
    name: str
    source_join_summary: str
    row_count: int


class TransformationStageResponse(BaseModel):
    rules_applied: list[str]
    rows_in: int
    rows_out: int
    derived_tables: list[DerivedTableSummary]


class LoadedTable(BaseModel):
    name: str
    row_count: int
    status: str                                # "loaded"


class LoadingStageResponse(BaseModel):
    target_tables: list[LoadedTable]


class RuleEngineStageResponse(BaseModel):
    kpi_type: str
    kpi_name: str
    pattern: str
    source_tables: list[str]
    conditions: list[str]                      # plain-English bullets from KpiDef
    rule_summary: str                          # 1-line "what it does"
    exceptions_generated: int
    total_evaluated: int
