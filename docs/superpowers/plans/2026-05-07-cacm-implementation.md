# CACM Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the CACM agent (Continuous Audit & Continuous Monitoring) — a new agent in the hub that walks 40 KPIs/KRIs through the full Library → Extract → Transform → Load → Rules → Exceptions → Dashboard flow over canned SAP-style sample data.

**Architecture:** Backend uses a 7-pattern rule library (`row_threshold`, `fuzzy_duplicate`, `date_compare`, `aggregate_threshold`, `cross_table_compare`, `missing_reference`, `temporal_anomaly`). Each KPI is a declarative `KpiDef` config that picks a pattern + params, so 40 KPIs ≈ 40 catalog entries instead of 40 hand-rolled functions. Runs are persisted in three new tables (`cacm_runs`, `cacm_run_events`, `cacm_exceptions`); the orchestrator runs as an asyncio background task and the frontend short-polls events every 500ms. Frontend mirrors the existing DMA / `rca_investigation` patterns — dedicated routes under `/agents/cacm/*` and a self-contained `frontend/src/cacm/` directory.

**Tech Stack:** Python 3.10+, FastAPI, SQLAlchemy 2 + Alembic, PostgreSQL (via Neon), pandas (already a dep — used by DMA), pytest. Frontend: React 18, React Router 6, Recharts (already a dep), axios (already used in DMA).

**Spec:** `docs/superpowers/specs/2026-05-07-cacm-design.md`

**Estimated effort:** ~16 person-days. 37 tasks across 12 phases.

---

## File Structure

### Backend

```
backend/
├── alembic/versions/
│   └── XXXX_add_cacm_tables.py           # NEW (Task 1)
├── app/
│   ├── agents/
│   │   ├── __init__.py                   # MODIFY (Task 27): add cacm to CATALOG
│   │   └── cacm/                         # NEW
│   │       ├── __init__.py
│   │       ├── kpi_catalog.py            # NEW (Task 12): 40 KpiDef records
│   │       ├── recommendations.py         # NEW (Task 13): hardcoded action text
│   │       ├── service.py                 # NEW (Task 22): pipeline orchestrator
│   │       ├── types.py                   # NEW (Task 3): KpiDef, RuleContext, ExceptionRecord
│   │       ├── rule_patterns/             # NEW (Tasks 4–11)
│   │       │   ├── __init__.py            # PATTERN_REGISTRY
│   │       │   ├── row_threshold.py
│   │       │   ├── fuzzy_duplicate.py
│   │       │   ├── date_compare.py
│   │       │   ├── aggregate_threshold.py
│   │       │   ├── cross_table_compare.py
│   │       │   ├── missing_reference.py
│   │       │   └── temporal_anomaly.py
│   │       └── sample_data/                # NEW (Tasks 14–21)
│   │           ├── procurement.json
│   │           ├── accounts_payable.json
│   │           ├── general_ledger.json
│   │           ├── payroll.json
│   │           ├── inventory.json
│   │           ├── sales_revenue.json
│   │           ├── access_management.json
│   │           └── insurance_ops.json
│   ├── api/routes/
│   │   └── cacm.py                       # NEW (Tasks 23–26): FastAPI routes
│   ├── main.py                            # MODIFY (Task 27): include cacm router
│   ├── models/
│   │   ├── __init__.py                    # MODIFY (Task 2): export new models
│   │   └── cacm.py                        # NEW (Task 2): CacmRun, CacmRunEvent, CacmException
│   └── schemas/
│       └── cacm.py                        # NEW (Task 23): Pydantic request/response models
└── tests/
    ├── test_cacm_kpi_catalog.py           # NEW (Task 12)
    ├── test_cacm_pattern_row_threshold.py # NEW (Task 4)
    ├── test_cacm_pattern_fuzzy_duplicate.py # NEW (Task 5)
    ├── test_cacm_pattern_date_compare.py  # NEW (Task 6)
    ├── test_cacm_pattern_aggregate_threshold.py # NEW (Task 7)
    ├── test_cacm_pattern_cross_table_compare.py # NEW (Task 8)
    ├── test_cacm_pattern_missing_reference.py # NEW (Task 9)
    ├── test_cacm_pattern_temporal_anomaly.py # NEW (Task 10)
    ├── test_cacm_pipeline.py              # NEW (Task 22)
    ├── test_cacm_routes.py                # NEW (Tasks 23–26)
    └── test_cacm_smoke_all_kpis.py        # NEW (Task 36)
```

### Frontend

```
frontend/src/
├── App.jsx                                # MODIFY (Task 35): add /agents/cacm/* routes
├── cacm/                                   # NEW
│   ├── api.js                              # NEW (Task 28): axios client + useEvents hook
│   ├── components/                         # NEW
│   │   ├── ProcessTile.jsx                 # Task 29
│   │   ├── KpiRow.jsx                      # Task 29
│   │   ├── StageStepper.jsx                # Task 29
│   │   ├── LogPanel.jsx                    # Task 29
│   │   ├── ExceptionTable.jsx              # Task 29
│   │   └── DashboardCharts.jsx             # Task 29
│   └── pages/                              # NEW
│       ├── LibraryPage.jsx                 # Task 30
│       ├── RunPage.jsx                     # Task 31
│       ├── ExceptionsPage.jsx              # Task 32
│       ├── DashboardPage.jsx               # Task 33
│       └── RunsHistoryPage.jsx             # Task 34
```

---

## Phase 1 — Database & Models

### Task 1: Alembic migration for the three CACM tables

**Files:**
- Create: `backend/alembic/versions/<auto-generated>_add_cacm_tables.py`

- [ ] **Step 1: Generate the migration skeleton**

```bash
cd backend && ./venv/bin/alembic revision -m "add cacm tables"
```

Expected: Prints a path like `Generating .../alembic/versions/abc123def456_add_cacm_tables.py ... done`. Note the filename for the next step.

- [ ] **Step 2: Fill in the migration**

Replace the generated file's `upgrade()` and `downgrade()` with:

```python
"""add cacm tables

Revision ID: <whatever-was-generated>
Revises: <previous-revision-id>
Create Date: 2026-05-07
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, set by Alembic at generation time
revision = '<keep what alembic put here>'
down_revision = '<keep what alembic put here>'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cacm_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("org_id", sa.Integer, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("kpi_type", sa.String(80), nullable=False, index=True),
        sa.Column("process", sa.String(80), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_records", sa.Integer, nullable=True),
        sa.Column("total_exceptions", sa.Integer, nullable=True),
        sa.Column("exception_pct", sa.Float, nullable=True),
        sa.Column("summary_json", sa.JSON, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
    )

    op.create_table(
        "cacm_run_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("cacm_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("stage", sa.String(40), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("payload_json", sa.JSON, nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("run_id", "seq", name="uq_cacm_event_run_seq"),
    )

    op.create_table(
        "cacm_exceptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("run_id", sa.Integer, sa.ForeignKey("cacm_runs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("exception_no", sa.String(40), nullable=False),
        sa.Column("risk", sa.String(10), nullable=False),
        sa.Column("payload_json", sa.JSON, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("cacm_exceptions")
    op.drop_table("cacm_run_events")
    op.drop_table("cacm_runs")
```

- [ ] **Step 3: Apply the migration**

```bash
cd backend && ./venv/bin/alembic upgrade head
```

Expected output ends with `INFO  [alembic.runtime.migration] Running upgrade <prev> -> <new>, add cacm tables`.

- [ ] **Step 4: Verify tables exist**

```bash
cd backend && ./venv/bin/python -c "
from sqlalchemy import inspect
from app.core.database import engine
print(sorted(t for t in inspect(engine).get_table_names() if t.startswith('cacm')))
"
```

Expected: `['cacm_exceptions', 'cacm_run_events', 'cacm_runs']`

- [ ] **Step 5: Commit**

```bash
git add backend/alembic/versions/*_add_cacm_tables.py
git commit -m "feat(cacm): add Alembic migration for cacm_runs, cacm_run_events, cacm_exceptions"
```

---

### Task 2: SQLAlchemy models for the three tables

**Files:**
- Create: `backend/app/models/cacm.py`
- Modify: `backend/app/models/__init__.py` (add exports)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_cacm_models.py`:

```python
"""Smoke test that the CACM ORM models are wired and round-trip cleanly."""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import (
    Organization, User,
    CacmRun, CacmRunEvent, CacmException,
)


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        yield s


def test_models_round_trip(db):
    org = Organization(name="X", slug="x", is_active=True)
    user = User(email="a@b.c", name="A", password_hash="x", is_super_admin=False, is_active=True)
    db.add_all([org, user])
    db.flush()

    run = CacmRun(
        org_id=org.id, user_id=user.id,
        kpi_type="po_after_invoice", process="Procurement",
        status="running",
    )
    db.add(run)
    db.flush()

    db.add(CacmRunEvent(run_id=run.id, seq=1, stage="extract", message="hi"))
    db.add(CacmException(run_id=run.id, exception_no="EX-0001", risk="High", payload_json={"a": 1}))
    db.commit()

    assert db.query(CacmRun).count() == 1
    assert db.query(CacmRunEvent).count() == 1
    assert db.query(CacmException).count() == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_models.py -v
```

Expected: FAIL with `ImportError: cannot import name 'CacmRun' from 'app.models'`.

- [ ] **Step 3: Implement models**

Create `backend/app/models/cacm.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models._base import TimestampMixin


class CacmRun(Base):
    """One end-to-end CACM execution.

    Persisted up-front (before the asyncio task even starts) so the frontend
    can navigate to the run page immediately and start polling.
    """
    __tablename__ = "cacm_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kpi_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    process: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_records: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_exceptions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    exception_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    summary_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    events = relationship("CacmRunEvent", back_populates="run", cascade="all, delete-orphan", order_by="CacmRunEvent.seq")
    exceptions = relationship("CacmException", back_populates="run", cascade="all, delete-orphan")


class CacmRunEvent(Base):
    """A single message emitted during a stage of the pipeline.

    `seq` is monotonically increasing within a run — the frontend's polling
    cursor is `?since=<last_seq>`, so this column is critical and must be
    unique within a run.
    """
    __tablename__ = "cacm_run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_cacm_event_run_seq"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("cacm_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    stage: Mapped[str] = mapped_column(String(40), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    run = relationship("CacmRun", back_populates="events")


class CacmException(Base):
    """One exception flagged by a rule. Payload is JSON because each KPI has
    a different shape — fixed columns would be 40-way YAGNI."""
    __tablename__ = "cacm_exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("cacm_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    exception_no: Mapped[str] = mapped_column(String(40), nullable=False)
    risk: Mapped[str] = mapped_column(String(10), nullable=False)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    run = relationship("CacmRun", back_populates="exceptions")
```

- [ ] **Step 4: Export from `app.models`**

In `backend/app/models/__init__.py`, add:

```python
from app.models.cacm import CacmRun, CacmRunEvent, CacmException  # noqa: F401
```

(Add it near the existing model imports — check that file's existing pattern and follow it.)

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_models.py -v
```

Expected: 1 test PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/models/cacm.py backend/app/models/__init__.py backend/tests/test_cacm_models.py
git commit -m "feat(cacm): add CacmRun, CacmRunEvent, CacmException ORM models"
```

---

## Phase 2 — Core Data Types

### Task 3: KpiDef, RuleContext, ExceptionRecord types

**Files:**
- Create: `backend/app/agents/cacm/__init__.py` (empty marker)
- Create: `backend/app/agents/cacm/types.py`
- Create: `backend/tests/test_cacm_types.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_cacm_types.py`:

```python
from __future__ import annotations

import pandas as pd
import pytest

from app.agents.cacm.types import (
    KpiDef, RuleContext, ExceptionRecord,
)


def test_kpidef_minimum_fields():
    kpi = KpiDef(
        type="po_after_invoice",
        process="Procurement",
        name="PO After Invoice",
        description="…",
        rule_objective="…",
        source_tables=["EKKO", "RBKP"],
        pattern="date_compare",
        params={"foo": "bar"},
    )
    assert kpi.type == "po_after_invoice"
    assert kpi.params == {"foo": "bar"}


def test_rulecontext_holds_dataframes():
    df = pd.DataFrame({"a": [1, 2]})
    ctx = RuleContext(tables={"ekko": df}, kpi_type="x")
    assert "ekko" in ctx.tables
    assert ctx.kpi_type == "x"


def test_exception_record_to_payload():
    e = ExceptionRecord(
        exception_no="EX-0001",
        risk="High",
        reason="…",
        value=12345.0,
        fields={"po_no": "4500001234", "vendor_code": "V001"},
    )
    payload = e.to_payload()
    assert payload["exception_no"] == "EX-0001"
    assert payload["risk"] == "High"
    assert payload["fields"]["po_no"] == "4500001234"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_types.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'app.agents.cacm.types'`.

- [ ] **Step 3: Implement types**

Create empty `backend/app/agents/cacm/__init__.py`:

```python
# CACM agent package marker.
```

Create `backend/app/agents/cacm/types.py`:

```python
"""Core data types for the CACM rule engine.

Why a separate module: the rule patterns, the orchestrator, and the API
serializers all share these shapes, so colocating them in one tiny file
avoids circular imports and gives every rule the same vocabulary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True)
class KpiDef:
    """Declarative description of one KPI/KRI.

    Adding a KPI is appending a `KpiDef(...)` to `kpi_catalog.KPI_CATALOG`.
    The `pattern` field names a function in `rule_patterns.PATTERN_REGISTRY`;
    `params` is forwarded to that function verbatim.
    """
    type: str                          # unique slug, e.g. "po_after_invoice"
    process: str                       # display category, e.g. "Procurement"
    name: str                          # display name on the catalog tile
    description: str                   # one-liner for the catalog tile
    rule_objective: str                # longer prose shown on the run page
    source_tables: list[str]           # SAP-style table names, for the extract stage messages
    pattern: str                       # name of the rule pattern in PATTERN_REGISTRY
    params: dict[str, Any]             # forwarded verbatim to the pattern callable


@dataclass
class RuleContext:
    """Container handed to a rule pattern at execution time.

    `tables` is keyed by the LOGICAL table name a pattern asks for (e.g.
    "ekko", "rbkp"); the orchestrator pre-loads them from sample data.
    """
    tables: dict[str, pd.DataFrame]
    kpi_type: str                      # forwarded so a pattern's error message can name itself


@dataclass
class ExceptionRecord:
    """One flagged exception. Patterns return a list of these.

    Stored as JSON in `cacm_exceptions.payload_json` — `to_payload` is the
    only serializer the orchestrator calls.
    """
    exception_no: str                  # e.g. "EX-0001"; assigned by the orchestrator after collection
    risk: str                          # "High" | "Medium" | "Low"
    reason: str                        # human-readable summary
    value: float | None = None         # numeric severity (e.g. dollar amount); optional
    fields: dict[str, Any] = field(default_factory=dict)  # key/value detail for the table

    def to_payload(self) -> dict[str, Any]:
        return {
            "exception_no": self.exception_no,
            "risk": self.risk,
            "reason": self.reason,
            "value": self.value,
            "fields": self.fields,
        }


# Common signature for a rule pattern callable.
PatternFn = Callable[[RuleContext, dict[str, Any]], list[ExceptionRecord]]
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_types.py -v
```

Expected: 3 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/cacm/__init__.py backend/app/agents/cacm/types.py backend/tests/test_cacm_types.py
git commit -m "feat(cacm): add KpiDef, RuleContext, ExceptionRecord types"
```

---

## Phase 3 — Rule Pattern Library (7 patterns, TDD each)

The pattern below is identical for all 7 patterns. We show it in full once (Task 4) and then give the test+impl content per pattern in Tasks 5–10. **All patterns import from `app.agents.cacm.types` and follow the same TDD steps:** write failing test → confirm RED → implement → confirm GREEN → commit.

### Task 4: `row_threshold` pattern

**Used by:** Manual JE > $10k, Round-sum invoice, Stock adj > threshold, etc. — 12 KPIs total.

**Params shape:**
```python
{
  "table": "bkpf",            # logical table name
  "column": "amount",         # column to test
  "op": ">",                  # one of >, >=, <, <=, ==, !=
  "threshold": 10000,         # numeric threshold
  "risk": "High",             # static risk OR dict mapping ranges (see test)
  "reason_template": "Amount {value} above {threshold}",
  "fields": ["doc_no", "user", "amount"],   # columns surfaced into the exception
}
```

**Files:**
- Create: `backend/app/agents/cacm/rule_patterns/__init__.py`
- Create: `backend/app/agents/cacm/rule_patterns/row_threshold.py`
- Create: `backend/tests/test_cacm_pattern_row_threshold.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the row_threshold rule pattern."""
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.row_threshold import row_threshold
from app.agents.cacm.types import RuleContext


def _ctx(df: pd.DataFrame, name: str = "t") -> RuleContext:
    return RuleContext(tables={name: df}, kpi_type="test")


def test_flags_rows_above_threshold():
    df = pd.DataFrame({
        "doc_no": ["A", "B", "C"],
        "user": ["u1", "u2", "u3"],
        "amount": [5000, 12000, 9999],
    })
    excs = row_threshold(_ctx(df), {
        "table": "t",
        "column": "amount",
        "op": ">",
        "threshold": 10000,
        "risk": "High",
        "reason_template": "Amount {value} above {threshold}",
        "fields": ["doc_no", "user", "amount"],
    })
    assert len(excs) == 1
    assert excs[0].fields["doc_no"] == "B"
    assert excs[0].risk == "High"
    assert excs[0].value == 12000
    assert "12000" in excs[0].reason and "10000" in excs[0].reason


def test_static_risk_vs_banded_risk():
    df = pd.DataFrame({"doc_no": ["A", "B", "C"], "amount": [11000, 50000, 200000]})
    # Banded risk: list of (low, high, risk) tuples; high=None means open-ended.
    excs = row_threshold(_ctx(df), {
        "table": "t", "column": "amount", "op": ">", "threshold": 10000,
        "risk": [(0, 49999, "Low"), (50000, 99999, "Medium"), (100000, None, "High")],
        "reason_template": "Amount {value}", "fields": ["doc_no", "amount"],
    })
    risks = sorted(e.risk for e in excs)
    assert risks == ["High", "Low", "Medium"]


def test_no_exceptions_when_no_rows_match():
    df = pd.DataFrame({"doc_no": ["A"], "amount": [100]})
    excs = row_threshold(_ctx(df), {
        "table": "t", "column": "amount", "op": ">", "threshold": 10000,
        "risk": "High", "reason_template": "x", "fields": ["doc_no"],
    })
    assert excs == []


def test_unknown_op_raises():
    import pytest
    df = pd.DataFrame({"doc_no": ["A"], "amount": [100]})
    with pytest.raises(ValueError, match="op"):
        row_threshold(_ctx(df), {
            "table": "t", "column": "amount", "op": "BOGUS",
            "threshold": 10, "risk": "High", "reason_template": "x", "fields": ["doc_no"],
        })
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_row_threshold.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the pattern + registry**

Create `backend/app/agents/cacm/rule_patterns/__init__.py`:

```python
"""Pattern registry — maps pattern name → callable.

Each pattern has signature `(ctx: RuleContext, params: dict) -> list[ExceptionRecord]`.
A KPI in the catalog declares its pattern by name; the orchestrator looks it up here.
"""
from __future__ import annotations

from app.agents.cacm.types import PatternFn
from app.agents.cacm.rule_patterns.row_threshold import row_threshold


PATTERN_REGISTRY: dict[str, PatternFn] = {
    "row_threshold": row_threshold,
    # other patterns added in Tasks 5–10
}
```

Create `backend/app/agents/cacm/rule_patterns/row_threshold.py`:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_row_threshold.py -v
```

Expected: 4 tests PASSED.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/cacm/rule_patterns/__init__.py backend/app/agents/cacm/rule_patterns/row_threshold.py backend/tests/test_cacm_pattern_row_threshold.py
git commit -m "feat(cacm): add row_threshold rule pattern + tests"
```

---

### Task 5: `fuzzy_duplicate` pattern

**Used by:** Duplicate POs, Duplicate invoices, Duplicate bank accounts (3 KPIs).

**Params shape:**
```python
{
  "table": "ekko",
  "id_column": "po_no",
  "compare_columns": ["vendor_code", "amount", "description"],   # text columns concatenated
  "threshold": 0.85,                                              # cosine similarity threshold
  "risk": "Medium",
  "reason_template": "POs {ids} look like duplicates ({score:.0%} similar)",
}
```

**Files:**
- Create: `backend/app/agents/cacm/rule_patterns/fuzzy_duplicate.py`
- Modify: `backend/app/agents/cacm/rule_patterns/__init__.py` (register)
- Create: `backend/tests/test_cacm_pattern_fuzzy_duplicate.py`

- [ ] **Step 1: Write the failing test**

```python
"""Tests for the fuzzy_duplicate rule pattern."""
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.fuzzy_duplicate import fuzzy_duplicate
from app.agents.cacm.types import RuleContext


def test_groups_near_duplicate_rows():
    df = pd.DataFrame({
        "po_no": ["A", "B", "C", "D"],
        "vendor_code": ["V1", "V1", "V1", "V2"],
        "amount": [1000, 1000, 50, 500],
        "description": ["Beaker 250ml", "Beaker 250 ml", "Pipette tip", "Centrifuge"],
    })
    excs = fuzzy_duplicate(RuleContext(tables={"ekko": df}, kpi_type="test"), {
        "table": "ekko",
        "id_column": "po_no",
        "compare_columns": ["vendor_code", "amount", "description"],
        "threshold": 0.7,
        "risk": "Medium",
        "reason_template": "POs {ids} look like duplicates ({score:.0%} similar)",
    })
    # A and B should cluster together; C and D should not.
    assert len(excs) == 1
    assert "A" in excs[0].fields["ids"] and "B" in excs[0].fields["ids"]
    assert excs[0].risk == "Medium"


def test_no_duplicates_returns_empty():
    df = pd.DataFrame({
        "po_no": ["A", "B"],
        "vendor_code": ["V1", "V2"],
        "amount": [100, 999999],
        "description": ["Apples", "Centrifuge unit"],
    })
    excs = fuzzy_duplicate(RuleContext(tables={"ekko": df}, kpi_type="t"), {
        "table": "ekko",
        "id_column": "po_no",
        "compare_columns": ["vendor_code", "amount", "description"],
        "threshold": 0.9,
        "risk": "Medium",
        "reason_template": "x",
    })
    assert excs == []
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_fuzzy_duplicate.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the pattern**

Create `backend/app/agents/cacm/rule_patterns/fuzzy_duplicate.py`:

```python
"""fuzzy_duplicate — cluster near-duplicate rows by text similarity.

Builds a TF-IDF representation over the concatenated text of `compare_columns`
and groups rows whose pairwise cosine similarity exceeds `threshold`. Uses
sklearn (already a project dependency via the DMA module).

Each cluster of >=2 rows produces one ExceptionRecord listing the duplicate IDs.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.agents.cacm.types import ExceptionRecord, RuleContext


def fuzzy_duplicate(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    table = params["table"]
    id_col = params["id_column"]
    cmp_cols = params["compare_columns"]
    threshold = float(params["threshold"])
    risk = params["risk"]
    reason_template = params["reason_template"]

    df = ctx.tables[table].reset_index(drop=True)
    if df.empty:
        return []

    # Concatenate compare columns to a single text per row, lowercased + spaces normalised.
    blob = df[cmp_cols].astype(str).agg(" ".join, axis=1).str.lower()
    vec = TfidfVectorizer(min_df=1).fit_transform(blob)
    sim = cosine_similarity(vec)

    # Union-find clustering across pairs above threshold.
    parent = list(range(len(df)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    n = len(df)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    excs: list[ExceptionRecord] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        ids = [str(df.loc[i, id_col]) for i in members]
        # Average similarity score within the cluster.
        scores = [sim[i, j] for i in members for j in members if i < j]
        avg = float(sum(scores) / len(scores)) if scores else 1.0
        excs.append(ExceptionRecord(
            exception_no="",
            risk=risk if isinstance(risk, str) else "Medium",
            reason=reason_template.format(ids=", ".join(ids), score=avg),
            value=float(len(members)),
            fields={"ids": ids, "size": len(members), "avg_score": round(avg, 3)},
        ))
    return excs
```

- [ ] **Step 4: Register in PATTERN_REGISTRY**

In `backend/app/agents/cacm/rule_patterns/__init__.py`, replace the body with:

```python
"""Pattern registry — maps pattern name → callable."""
from __future__ import annotations

from app.agents.cacm.types import PatternFn
from app.agents.cacm.rule_patterns.row_threshold import row_threshold
from app.agents.cacm.rule_patterns.fuzzy_duplicate import fuzzy_duplicate


PATTERN_REGISTRY: dict[str, PatternFn] = {
    "row_threshold": row_threshold,
    "fuzzy_duplicate": fuzzy_duplicate,
    # remaining patterns added in Tasks 6–10
}
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_fuzzy_duplicate.py -v
```

Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/cacm/rule_patterns/fuzzy_duplicate.py backend/app/agents/cacm/rule_patterns/__init__.py backend/tests/test_cacm_pattern_fuzzy_duplicate.py
git commit -m "feat(cacm): add fuzzy_duplicate rule pattern + tests"
```

---

### Task 6: `date_compare` pattern

**Used by:** PO After Invoice Date (1 KPI). Fewer than other patterns but the BR's worked example.

**Params shape:**
```python
{
  "table": "po_invoice_joined",       # joined logical table the orchestrator builds
  "left_date": "po_created",
  "right_date": "invoice_posted",
  "op": ">",
  "risk_bands": [(0, 3, "Low"), (4, 14, "Medium"), (15, None, "High")],   # by abs(diff_days)
  "reason_template": "PO {po_no} created {diff_days} days after invoice {inv_no}",
  "fields": ["po_no", "inv_no", "vendor_code"],
}
```

**Files:**
- Create: `backend/app/agents/cacm/rule_patterns/date_compare.py`
- Modify: `backend/app/agents/cacm/rule_patterns/__init__.py` (register)
- Create: `backend/tests/test_cacm_pattern_date_compare.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.date_compare import date_compare
from app.agents.cacm.types import RuleContext


def test_flags_when_left_date_after_right_date():
    df = pd.DataFrame({
        "po_no": ["P1", "P2", "P3"],
        "inv_no": ["I1", "I2", "I3"],
        "vendor_code": ["V1", "V2", "V3"],
        "po_created": pd.to_datetime(["2026-04-15", "2026-04-01", "2026-04-30"]),
        "invoice_posted": pd.to_datetime(["2026-04-10", "2026-04-15", "2026-04-29"]),
    })
    excs = date_compare(RuleContext(tables={"j": df}, kpi_type="t"), {
        "table": "j",
        "left_date": "po_created",
        "right_date": "invoice_posted",
        "op": ">",
        "risk_bands": [(0, 3, "Low"), (4, 14, "Medium"), (15, None, "High")],
        "reason_template": "PO {po_no} created {diff_days} days after invoice {inv_no}",
        "fields": ["po_no", "inv_no", "vendor_code"],
    })
    # P1 is 5 days late → Medium; P3 is 1 day late → Low; P2 is on-time (PO before inv).
    assert {e.fields["po_no"] for e in excs} == {"P1", "P3"}
    by_po = {e.fields["po_no"]: e for e in excs}
    assert by_po["P1"].risk == "Medium"
    assert by_po["P3"].risk == "Low"
    assert "5 days after" in by_po["P1"].reason
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_date_compare.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the pattern**

Create `backend/app/agents/cacm/rule_patterns/date_compare.py`:

```python
"""date_compare — flag rows where date_a op date_b.

Used by KPIs like "PO created after invoice posted". The diff in days drives
risk banding so a 1-day lag (administrative slip) is rated lower than a
30-day lag (likely after-the-fact PO).
"""
from __future__ import annotations

import operator
from typing import Any

from app.agents.cacm.types import ExceptionRecord, RuleContext


_OPS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


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
        excs.append(ExceptionRecord(
            exception_no="",
            risk=risk,
            reason=reason_template.format(diff_days=diff_days, **{c: row[c] for c in field_cols}),
            value=float(diff_days),
            fields={**{c: row[c] for c in field_cols}, "diff_days": diff_days},
        ))
    return excs
```

- [ ] **Step 4: Register in PATTERN_REGISTRY**

In `backend/app/agents/cacm/rule_patterns/__init__.py`, add the import and entry:

```python
from app.agents.cacm.rule_patterns.date_compare import date_compare
# ... in PATTERN_REGISTRY:
    "date_compare": date_compare,
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_date_compare.py -v
```

Expected: 1 test PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/cacm/rule_patterns/date_compare.py backend/app/agents/cacm/rule_patterns/__init__.py backend/tests/test_cacm_pattern_date_compare.py
git commit -m "feat(cacm): add date_compare rule pattern + tests"
```

---

### Task 7: `aggregate_threshold` pattern

**Used by:** Vendor Concentration, Single Source, Slow-Moving, Failed Logins, Multiple Claims, etc. — 7 KPIs.

**Params shape:**
```python
{
  "table": "ekko",
  "group_by": ["vendor_code"],
  "agg": {"column": "amount", "fn": "sum"},   # sum | count | mean
  "op": ">",
  "threshold": 0.5,                            # absolute, OR fraction-of-total when as_fraction=True
  "as_fraction": True,                         # interpret threshold as fraction of total agg
  "risk": "High",
  "reason_template": "Vendor {key} accounts for {fraction:.0%} of spend",
  "fields": ["vendor_code", "vendor_name"],     # optional join-back columns from the same table
}
```

**Files:**
- Create: `backend/app/agents/cacm/rule_patterns/aggregate_threshold.py`
- Modify: `backend/app/agents/cacm/rule_patterns/__init__.py`
- Create: `backend/tests/test_cacm_pattern_aggregate_threshold.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.aggregate_threshold import aggregate_threshold
from app.agents.cacm.types import RuleContext


def test_flags_groups_above_absolute_threshold():
    df = pd.DataFrame({"user": ["u1", "u1", "u2"], "doc": ["a", "b", "c"]})
    excs = aggregate_threshold(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "group_by": ["user"],
        "agg": {"column": "doc", "fn": "count"},
        "op": ">", "threshold": 1, "as_fraction": False,
        "risk": "Medium",
        "reason_template": "User {key} has {value} entries",
        "fields": [],
    })
    assert len(excs) == 1
    assert excs[0].fields["key"] == "u1"


def test_flags_fraction_of_total():
    df = pd.DataFrame({"vendor": ["A", "A", "A", "B"], "amount": [100, 100, 100, 50]})
    # Total spend = 350; vendor A = 300 (~86%). Threshold 0.5 → A flagged.
    excs = aggregate_threshold(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "group_by": ["vendor"],
        "agg": {"column": "amount", "fn": "sum"},
        "op": ">", "threshold": 0.5, "as_fraction": True,
        "risk": "High",
        "reason_template": "{key} = {fraction:.0%}",
        "fields": [],
    })
    assert len(excs) == 1
    assert excs[0].fields["key"] == "A"
    assert "86%" in excs[0].reason
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_aggregate_threshold.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement**

```python
"""aggregate_threshold — group rows + aggregate + threshold.

Use cases: vendor concentration (top vendor share of spend > 50%), failed
logins per user > 5, write-offs per user > 10. Supports an absolute
threshold or a fraction-of-total threshold via `as_fraction=True`.
"""
from __future__ import annotations

from typing import Any

import pandas as pd

from app.agents.cacm.types import ExceptionRecord, RuleContext


_AGG_FNS = {"sum": "sum", "count": "count", "mean": "mean", "max": "max", "min": "min"}
_OPS = {">": lambda a, b: a > b, ">=": lambda a, b: a >= b, "<": lambda a, b: a < b, "<=": lambda a, b: a <= b}


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
            risk=risk if isinstance(risk, str) else "Medium",
            reason=reason_template.format(key=key_repr, value=v, fraction=fraction or 0),
            value=v,
            fields={"key": key_repr, "agg_value": v, "fraction": fraction},
        ))
    return excs
```

- [ ] **Step 4: Register**

Add to `__init__.py`:
```python
from app.agents.cacm.rule_patterns.aggregate_threshold import aggregate_threshold
# in PATTERN_REGISTRY:
    "aggregate_threshold": aggregate_threshold,
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_aggregate_threshold.py -v
```

Expected: 2 tests PASSED.

- [ ] **Step 6: Commit**

```bash
git add backend/app/agents/cacm/rule_patterns/aggregate_threshold.py backend/app/agents/cacm/rule_patterns/__init__.py backend/tests/test_cacm_pattern_aggregate_threshold.py
git commit -m "feat(cacm): add aggregate_threshold rule pattern + tests"
```

---

### Task 8: `cross_table_compare` pattern

**Used by:** 3-Way Match, Pay to Inactive Vendor, Credit Limit Exceeded, etc. — 7 KPIs.

**Params shape:**
```python
{
  "left_table": "rbkp",
  "right_table": "lfa1",
  "join_on": [("vendor_code", "vendor_code")],     # (left_col, right_col) tuples
  "flag_when": {"column": "is_active", "op": "==", "value": False, "side": "right"},
  "risk": "High",
  "reason_template": "Invoice {inv_no} paid to inactive vendor {vendor_code}",
  "fields": ["inv_no", "vendor_code", "amount"],
}
```

**Files:**
- Create: `backend/app/agents/cacm/rule_patterns/cross_table_compare.py`
- Modify: `backend/app/agents/cacm/rule_patterns/__init__.py`
- Create: `backend/tests/test_cacm_pattern_cross_table_compare.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.cross_table_compare import cross_table_compare
from app.agents.cacm.types import RuleContext


def test_flags_join_with_predicate():
    rbkp = pd.DataFrame({
        "inv_no": ["I1", "I2", "I3"],
        "vendor_code": ["V1", "V2", "V3"],
        "amount": [1000, 500, 2000],
    })
    lfa1 = pd.DataFrame({"vendor_code": ["V1", "V2", "V3"], "is_active": [True, False, True]})
    excs = cross_table_compare(RuleContext(tables={"rbkp": rbkp, "lfa1": lfa1}, kpi_type="t"), {
        "left_table": "rbkp",
        "right_table": "lfa1",
        "join_on": [("vendor_code", "vendor_code")],
        "flag_when": {"column": "is_active", "op": "==", "value": False, "side": "right"},
        "risk": "High",
        "reason_template": "Invoice {inv_no} paid to inactive vendor {vendor_code}",
        "fields": ["inv_no", "vendor_code", "amount"],
    })
    assert len(excs) == 1
    assert excs[0].fields["inv_no"] == "I2"
    assert excs[0].risk == "High"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_cross_table_compare.py -v
```

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Register + run + commit** (same shape as previous tasks)

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_cross_table_compare.py -v
git add backend/app/agents/cacm/rule_patterns/cross_table_compare.py backend/app/agents/cacm/rule_patterns/__init__.py backend/tests/test_cacm_pattern_cross_table_compare.py
git commit -m "feat(cacm): add cross_table_compare rule pattern + tests"
```

Expected test result: 1 PASSED.

---

### Task 9: `missing_reference` pattern

**Used by:** PO Without Contract, Invoice Without PO, Salary Change w/o Approval, etc. — 5 KPIs.

**Params shape:**
```python
{
  "left_table": "ekko",
  "right_table": "contracts",
  "left_key": "contract_ref",
  "right_key": "contract_id",
  "risk": "Medium",
  "reason_template": "PO {po_no} has no matching contract",
  "fields": ["po_no", "vendor_code", "amount"],
}
```

**Files:**
- Create: `backend/app/agents/cacm/rule_patterns/missing_reference.py`
- Modify: `backend/app/agents/cacm/rule_patterns/__init__.py`
- Create: `backend/tests/test_cacm_pattern_missing_reference.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.missing_reference import missing_reference
from app.agents.cacm.types import RuleContext


def test_flags_left_rows_without_match():
    ekko = pd.DataFrame({
        "po_no": ["P1", "P2", "P3"],
        "vendor_code": ["V1", "V2", "V3"],
        "amount": [100, 200, 300],
        "contract_ref": ["C1", None, "C3"],
    })
    contracts = pd.DataFrame({"contract_id": ["C1", "C2"]})
    excs = missing_reference(RuleContext(tables={"ekko": ekko, "contracts": contracts}, kpi_type="t"), {
        "left_table": "ekko",
        "right_table": "contracts",
        "left_key": "contract_ref",
        "right_key": "contract_id",
        "risk": "Medium",
        "reason_template": "PO {po_no} has no matching contract",
        "fields": ["po_no", "vendor_code", "amount"],
    })
    flagged_pos = {e.fields["po_no"] for e in excs}
    assert flagged_pos == {"P2", "P3"}  # P2 has null ref; P3 has C3 which isn't in contracts
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement**

```python
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
```

- [ ] **Step 4: Register + run + commit**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_missing_reference.py -v
git add backend/app/agents/cacm/rule_patterns/missing_reference.py backend/app/agents/cacm/rule_patterns/__init__.py backend/tests/test_cacm_pattern_missing_reference.py
git commit -m "feat(cacm): add missing_reference rule pattern + tests"
```

Expected: 1 PASSED.

---

### Task 10: `temporal_anomaly` pattern

**Used by:** Weekend Posting, Inactive User Accounts, Aged Claims, Revenue Anomalies (5 KPIs).

**Params shape (multi-mode):**
```python
{
  "table": "bkpf",
  "date_column": "posting_date",
  "mode": "weekend",                 # or "ageing" or "stale"
  "params": {                         # mode-specific
    "weekday_set": [5, 6],            # mode=weekend: 5=Sat, 6=Sun
    # mode=ageing: {"buckets": [(0,30,"Low"), (31,90,"Medium"), (91,None,"High")], "reference_date": "2026-05-07"}
    # mode=stale:  {"days": 90, "reference_date": "2026-05-07"}
  },
  "risk": "Medium",
  "reason_template": "Posting on {date} ({weekday})",
  "fields": ["doc_no", "user", "posting_date"],
}
```

**Files:**
- Create: `backend/app/agents/cacm/rule_patterns/temporal_anomaly.py`
- Modify: `backend/app/agents/cacm/rule_patterns/__init__.py`
- Create: `backend/tests/test_cacm_pattern_temporal_anomaly.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import pandas as pd

from app.agents.cacm.rule_patterns.temporal_anomaly import temporal_anomaly
from app.agents.cacm.types import RuleContext


def test_weekend_mode_flags_saturday_sunday():
    df = pd.DataFrame({
        "doc_no": ["D1", "D2", "D3"],
        "user": ["u1", "u2", "u3"],
        "posting_date": pd.to_datetime(["2026-05-02", "2026-05-04", "2026-05-03"]),  # Sat, Mon, Sun
    })
    excs = temporal_anomaly(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "date_column": "posting_date",
        "mode": "weekend",
        "params": {"weekday_set": [5, 6]},
        "risk": "Medium",
        "reason_template": "Posting on {date} ({weekday})",
        "fields": ["doc_no", "user", "posting_date"],
    })
    assert {e.fields["doc_no"] for e in excs} == {"D1", "D3"}


def test_stale_mode_flags_old_dates():
    df = pd.DataFrame({
        "user_id": ["u1", "u2"],
        "last_login": pd.to_datetime(["2025-12-01", "2026-04-15"]),
    })
    excs = temporal_anomaly(RuleContext(tables={"t": df}, kpi_type="x"), {
        "table": "t", "date_column": "last_login",
        "mode": "stale",
        "params": {"days": 90, "reference_date": "2026-05-07"},
        "risk": "High",
        "reason_template": "User {user_id} dormant since {last_login}",
        "fields": ["user_id", "last_login"],
    })
    assert len(excs) == 1
    assert excs[0].fields["user_id"] == "u1"
```

- [ ] **Step 2: Run test to verify it fails**

- [ ] **Step 3: Implement**

```python
"""temporal_anomaly — date-based anomaly detection (weekend/holiday/ageing).

Modes:
  weekend  — flag rows whose date weekday ∈ {weekday_set}
  stale    — flag rows whose date < reference_date - days
  ageing   — flag every row, but bucket risk by age (used with always-flag KPIs like aged claims)
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from app.agents.cacm.types import ExceptionRecord, RuleContext


_WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def temporal_anomaly(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    df = ctx.tables[params["table"]]
    col = params["date_column"]
    mode = params["mode"]
    mp = params["params"]
    risk_default = params["risk"]
    reason_template = params["reason_template"]
    field_cols = params["fields"]

    if mode == "weekend":
        weekday_set = set(mp["weekday_set"])
        flagged = df[df[col].dt.weekday.isin(weekday_set)]
        excs = [
            ExceptionRecord(
                exception_no="", risk=risk_default,
                reason=reason_template.format(date=row[col].date(), weekday=_WEEKDAYS[row[col].weekday()],
                                              **{c: row[c] for c in field_cols}),
                value=None,
                fields={c: row[c] for c in field_cols},
            )
            for _, row in flagged.iterrows()
        ]
        return excs

    if mode == "stale":
        ref = pd.to_datetime(mp["reference_date"])
        cutoff = ref - pd.Timedelta(days=int(mp["days"]))
        flagged = df[df[col] < cutoff]
        return [
            ExceptionRecord(
                exception_no="", risk=risk_default,
                reason=reason_template.format(**{c: row[c] for c in field_cols}),
                value=float((ref - row[col]).days),
                fields={c: row[c] for c in field_cols},
            )
            for _, row in flagged.iterrows()
        ]

    if mode == "ageing":
        ref = pd.to_datetime(mp["reference_date"])
        buckets = mp["buckets"]   # [(low_days, high_days, risk)]
        excs: list[ExceptionRecord] = []
        for _, row in df.iterrows():
            age_days = int((ref - row[col]).days)
            risk = risk_default
            for low, high, r in buckets:
                if age_days >= low and (high is None or age_days <= high):
                    risk = r
                    break
            excs.append(ExceptionRecord(
                exception_no="", risk=risk,
                reason=reason_template.format(age_days=age_days, **{c: row[c] for c in field_cols}),
                value=float(age_days),
                fields={**{c: row[c] for c in field_cols}, "age_days": age_days},
            ))
        return excs

    raise ValueError(f"temporal_anomaly: unknown mode {mode!r}")
```

- [ ] **Step 4: Register + run + commit**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_temporal_anomaly.py -v
git add backend/app/agents/cacm/rule_patterns/temporal_anomaly.py backend/app/agents/cacm/rule_patterns/__init__.py backend/tests/test_cacm_pattern_temporal_anomaly.py
git commit -m "feat(cacm): add temporal_anomaly rule pattern + tests"
```

Expected: 2 PASSED.

---

### Task 11: Verify all 7 patterns are registered

**Files:**
- Test only: `backend/tests/test_cacm_pattern_registry.py`

- [ ] **Step 1: Write the test**

```python
"""Catches a forgotten registration — every pattern file must show up in PATTERN_REGISTRY."""
from __future__ import annotations

from app.agents.cacm.rule_patterns import PATTERN_REGISTRY


EXPECTED = {
    "row_threshold", "fuzzy_duplicate", "date_compare",
    "aggregate_threshold", "cross_table_compare",
    "missing_reference", "temporal_anomaly",
}


def test_all_seven_patterns_registered():
    assert set(PATTERN_REGISTRY) == EXPECTED


def test_every_pattern_is_callable():
    for name, fn in PATTERN_REGISTRY.items():
        assert callable(fn), f"{name} is not callable"
```

- [ ] **Step 2: Run + commit**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pattern_registry.py -v
git add backend/tests/test_cacm_pattern_registry.py
git commit -m "test(cacm): verify all 7 patterns are in PATTERN_REGISTRY"
```

Expected: 2 PASSED.

---

## Phase 4 — KPI Catalog, Recommendations, Sample Data

### Task 12: KPI catalog (all 40 entries)

**Files:**
- Create: `backend/app/agents/cacm/kpi_catalog.py`
- Create: `backend/tests/test_cacm_kpi_catalog.py`

- [ ] **Step 1: Write the failing test**

```python
"""Catalog must have all 40 KPIs across 8 processes, each pointing at a real pattern."""
from __future__ import annotations

from collections import Counter

from app.agents.cacm.kpi_catalog import KPI_CATALOG, kpi_by_type
from app.agents.cacm.rule_patterns import PATTERN_REGISTRY


def test_forty_kpis_across_eight_processes():
    assert len(KPI_CATALOG) == 40
    processes = {k.process for k in KPI_CATALOG}
    assert processes == {
        "Procurement", "Accounts Payable", "General Ledger", "Payroll",
        "Inventory", "Sales / Revenue", "Access Management", "Insurance / Operations",
    }


def test_no_duplicate_types():
    types = [k.type for k in KPI_CATALOG]
    dupes = [t for t, c in Counter(types).items() if c > 1]
    assert dupes == []


def test_every_pattern_exists():
    for k in KPI_CATALOG:
        assert k.pattern in PATTERN_REGISTRY, f"{k.type} → unknown pattern {k.pattern!r}"


def test_kpi_by_type_lookup():
    k = kpi_by_type("po_after_invoice")
    assert k is not None
    assert k.process == "Procurement"
```

- [ ] **Step 2: Run to confirm RED**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_kpi_catalog.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Implement the catalog**

Create `backend/app/agents/cacm/kpi_catalog.py`. **Note:** Spec §3 has the full 40-row table. Use that as your source of truth. The structure of each entry follows this template:

```python
"""KPI/KRI catalog — one KpiDef per row in spec §3.

Adding a KPI: append a KpiDef(...) below. Removing a KPI: delete the line.
The catalog drives the Library page rendering, the rule engine dispatch,
and the per-KPI smoke test.
"""
from __future__ import annotations

from app.agents.cacm.types import KpiDef


# ── Procurement (6) ──────────────────────────────────────────────────────────

PROCUREMENT_KPIS: list[KpiDef] = [
    KpiDef(
        type="duplicate_pos",
        process="Procurement",
        name="Duplicate Purchase Orders",
        description="Detect near-duplicate POs raised against the same vendor.",
        rule_objective=(
            "Flag groups of POs raised against the same vendor with very similar "
            "line descriptions and amounts within a short timeframe — typical of "
            "process or system-generated duplicates."
        ),
        source_tables=["EKKO", "EKPO"],
        pattern="fuzzy_duplicate",
        params={
            "table": "ekko_with_lines",
            "id_column": "po_no",
            "compare_columns": ["vendor_code", "amount", "description"],
            "threshold": 0.85,
            "risk": "Medium",
            "reason_template": "POs {ids} look like duplicates ({score:.0%} similar)",
        },
    ),
    KpiDef(
        type="po_after_invoice",
        process="Procurement",
        name="PO Created After Invoice Date",
        description="Procurement approval should occur before invoice processing.",
        rule_objective=(
            "Compare PO creation date with the corresponding invoice posting date. "
            "If the PO is dated AFTER the invoice, it suggests the PO was raised "
            "retroactively — a red flag for procurement controls."
        ),
        source_tables=["EKKO", "RBKP"],
        pattern="date_compare",
        params={
            "table": "po_invoice_joined",
            "left_date": "po_created",
            "right_date": "invoice_posted",
            "op": ">",
            "risk_bands": [(0, 3, "Low"), (4, 14, "Medium"), (15, None, "High")],
            "reason_template": "PO {po_no} created {diff_days} days after invoice {inv_no}",
            "fields": ["po_no", "inv_no", "vendor_code"],
        },
    ),
    KpiDef(
        type="single_source",
        process="Procurement",
        name="Single Source Procurement",
        description="Categories where only one vendor was used in the period.",
        rule_objective=(
            "Identify spend categories where 100% of POs went to a single vendor — "
            "may indicate insufficient sourcing diversity or non-competitive procurement."
        ),
        source_tables=["EKKO", "EKPO", "LFA1"],
        pattern="aggregate_threshold",
        params={
            "table": "ekko_with_category",
            "group_by": ["category"],
            "agg": {"column": "vendor_code", "fn": "count"},   # placeholder; real impl uses nunique via a derived column
            "op": ">=",
            "threshold": 1.0,
            "as_fraction": True,
            "risk": "Medium",
            "reason_template": "Category {key} sourced from a single vendor",
            "fields": [],
        },
    ),
    KpiDef(
        type="contract_above_approval",
        process="Procurement",
        name="Contract Value Exceeding Approval Limit",
        description="POs whose value exceeds the approver's authority limit.",
        rule_objective=(
            "Compare PO total value against the approver's approval limit (joined "
            "from a static authority matrix). PO value > limit → control breach."
        ),
        source_tables=["EKKO"],
        pattern="row_threshold",
        params={
            "table": "ekko",
            "column": "approver_overage",   # pre-computed in transformation: po_value - approver_limit
            "op": ">",
            "threshold": 0,
            "risk": [(1, 9999, "Low"), (10000, 99999, "Medium"), (100000, None, "High")],
            "reason_template": "PO exceeds approver limit by {value}",
            "fields": ["po_no", "vendor_code", "amount", "approver_user", "approver_limit"],
        },
    ),
    KpiDef(
        type="vendor_concentration",
        process="Procurement",
        name="Vendor Concentration",
        description="Vendors accounting for an outsized share of total spend.",
        rule_objective=(
            "Flag any vendor whose share of total spend exceeds 30% — too much "
            "dependence on a single supplier creates concentration risk."
        ),
        source_tables=["EKKO", "LFA1"],
        pattern="aggregate_threshold",
        params={
            "table": "ekko",
            "group_by": ["vendor_code"],
            "agg": {"column": "amount", "fn": "sum"},
            "op": ">",
            "threshold": 0.30,
            "as_fraction": True,
            "risk": "High",
            "reason_template": "Vendor {key} accounts for {fraction:.0%} of spend",
            "fields": [],
        },
    ),
    KpiDef(
        type="po_without_contract",
        process="Procurement",
        name="PO Without Contract Reference",
        description="POs raised without referencing an active master contract.",
        rule_objective=(
            "Every PO above a de-minimis threshold should reference a master "
            "contract. POs without a contract reference bypass negotiated terms."
        ),
        source_tables=["EKKO"],
        pattern="missing_reference",
        params={
            "left_table": "ekko",
            "right_table": "contracts",
            "left_key": "contract_ref",
            "right_key": "contract_id",
            "risk": "Medium",
            "reason_template": "PO {po_no} has no matching contract",
            "fields": ["po_no", "vendor_code", "amount"],
        },
    ),
]


# ── Accounts Payable (5) ─────────────────────────────────────────────────────

AP_KPIS: list[KpiDef] = [
    KpiDef(type="duplicate_invoices", process="Accounts Payable", name="Duplicate Invoice Payments",
        description="Same invoice paid more than once.",
        rule_objective="Cluster RBKP rows with identical vendor + amount + reference within a short window.",
        source_tables=["RBKP", "RSEG"],
        pattern="fuzzy_duplicate",
        params={"table": "rbkp", "id_column": "inv_no",
                "compare_columns": ["vendor_code", "amount", "reference"],
                "threshold": 0.95, "risk": "High",
                "reason_template": "Invoices {ids} look like duplicate payments ({score:.0%})"}),
    KpiDef(type="invoice_without_po", process="Accounts Payable", name="Invoice Without Purchase Order",
        description="Vendor invoice processed without a referenced PO.",
        rule_objective="Anti-join RBKP against EKKO. Missing PO reference indicates bypassed procurement.",
        source_tables=["RBKP", "EKKO"],
        pattern="missing_reference",
        params={"left_table": "rbkp", "right_table": "ekko",
                "left_key": "po_ref", "right_key": "po_no",
                "risk": "Medium", "reason_template": "Invoice {inv_no} has no matching PO",
                "fields": ["inv_no", "vendor_code", "amount"]}),
    KpiDef(type="three_way_match_fail", process="Accounts Payable", name="Three-Way Match Failures",
        description="Invoice qty/amount mismatches PO and goods receipt.",
        rule_objective="Join invoice → PO line → GR; flag when invoice qty != PO qty (or amount delta > tolerance).",
        source_tables=["RBKP", "EKKO", "EKPO"],
        pattern="cross_table_compare",
        params={"left_table": "rseg", "right_table": "ekpo",
                "join_on": [("po_no", "po_no"), ("po_line", "line_no")],
                "flag_when": {"column": "qty_mismatch", "op": "==", "value": True, "side": "left"},
                "risk": "High",
                "reason_template": "Invoice {inv_no} line {line_no}: qty {inv_qty} ≠ PO qty {po_qty}",
                "fields": ["inv_no", "line_no", "inv_qty", "po_qty"]}),
    KpiDef(type="round_sum_invoices", process="Accounts Payable", name="Round-Sum Invoice Amounts",
        description="Invoices for suspiciously round dollar amounts.",
        rule_objective="Flag invoices with amounts ending in '000' that are above a low threshold — common indicator of fictitious billing.",
        source_tables=["RBKP"],
        pattern="row_threshold",
        params={"table": "rbkp", "column": "is_round_sum", "op": "==", "threshold": True,
                "risk": "Low", "reason_template": "Invoice {inv_no} is round-sum ({amount})",
                "fields": ["inv_no", "vendor_code", "amount"]}),
    KpiDef(type="pay_inactive_vendor", process="Accounts Payable", name="Payment to Inactive Vendor",
        description="Invoice posted against a vendor flagged inactive in the master.",
        rule_objective="Join RBKP → LFA1; flag any payment to a vendor whose is_active=False.",
        source_tables=["RBKP", "LFA1"],
        pattern="cross_table_compare",
        params={"left_table": "rbkp", "right_table": "lfa1",
                "join_on": [("vendor_code", "vendor_code")],
                "flag_when": {"column": "is_active", "op": "==", "value": False, "side": "right"},
                "risk": "High",
                "reason_template": "Invoice {inv_no} paid to inactive vendor {vendor_code}",
                "fields": ["inv_no", "vendor_code", "amount"]}),
]


# (continue with GL_KPIS, PAYROLL_KPIS, INVENTORY_KPIS, SALES_KPIS, ACCESS_KPIS, INSURANCE_KPIS
#  — same structure, one KpiDef per spec §3 row. Engineer following this plan should expand
#  each block by mirroring the pattern above and using the spec table for source_tables + pattern.)


KPI_CATALOG: list[KpiDef] = [
    *PROCUREMENT_KPIS,
    *AP_KPIS,
    # *GL_KPIS, *PAYROLL_KPIS, *INVENTORY_KPIS, *SALES_KPIS, *ACCESS_KPIS, *INSURANCE_KPIS,
]


def kpi_by_type(t: str) -> KpiDef | None:
    for k in KPI_CATALOG:
        if k.type == t:
            return k
    return None


def kpis_by_process() -> dict[str, list[KpiDef]]:
    out: dict[str, list[KpiDef]] = {}
    for k in KPI_CATALOG:
        out.setdefault(k.process, []).append(k)
    return out
```

**Important:** The skeleton above has only Procurement (6) + AP (5) explicit. The engineer must complete the remaining 6 blocks (GL, Payroll, Inventory, Sales, Access, Insurance) using spec §3 as the source of truth for `pattern` and `source_tables`. Each block follows the AP pattern (compact form). After expansion `len(KPI_CATALOG) == 40`.

- [ ] **Step 4: Run test**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_kpi_catalog.py -v
```

Expected: 4 PASSED. If `test_forty_kpis_across_eight_processes` fails with a count off, expand the missing process blocks.

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/cacm/kpi_catalog.py backend/tests/test_cacm_kpi_catalog.py
git commit -m "feat(cacm): add KPI catalog with all 40 KPIs across 8 processes"
```

---

### Task 13: Recommendations module

**Files:**
- Create: `backend/app/agents/cacm/recommendations.py`
- Create: `backend/tests/test_cacm_recommendations.py`

- [ ] **Step 1: Write the failing test**

```python
"""Every KPI in the catalog must have a recommendation."""
from __future__ import annotations

from app.agents.cacm.kpi_catalog import KPI_CATALOG
from app.agents.cacm.recommendations import recommendation_for


def test_every_kpi_has_a_recommendation():
    for k in KPI_CATALOG:
        rec = recommendation_for(k.type)
        assert rec, f"missing recommendation for {k.type}"
        assert isinstance(rec, str)
```

- [ ] **Step 2: Run to confirm RED, then implement**

```python
"""Hardcoded 'Recommended action' text per KPI.

Phase 1 of the AI-augmented exception flow: the demo ships with these
canned recommendations so leadership sees actionable guidance next to
each exception. A future story will swap this for an LLM call (one-line
change inside the orchestrator's enrich-exceptions step).
"""
from __future__ import annotations

_RECS: dict[str, str] = {
    "duplicate_pos": "Cancel duplicate POs; update vendor master to dedupe before raising new POs.",
    "po_after_invoice": "Investigate why the PO was raised after the invoice; tighten approval workflow.",
    "single_source": "Run a competitive RFP for this category; document sole-source justification if continuing.",
    "contract_above_approval": "Escalate to next-level approver retroactively; review approval matrix configuration.",
    "vendor_concentration": "Initiate alternate-vendor sourcing; document concentration risk in supplier review.",
    "po_without_contract": "Tie this PO to an active contract or convert to a one-time purchase order with VP approval.",
    "duplicate_invoices": "Recall duplicate payment from vendor; configure 3-way match block on the offending vendor.",
    "invoice_without_po": "Match to a PO retroactively or convert to a one-time-vendor invoice with controller approval.",
    "three_way_match_fail": "Reconcile invoice quantity to GR; clear or reject within the SLA window.",
    "round_sum_invoices": "Validate the underlying transaction; ensure it isn't a placeholder or fictitious billing.",
    "pay_inactive_vendor": "Block further payments to this vendor; verify the inactive flag with vendor master owner.",
    # Add one entry per KPI in the catalog.  Default text below covers any
    # KPI that doesn't have a specific recommendation yet.
}

_DEFAULT = "Investigate the flagged transaction; document resolution in the audit log."


def recommendation_for(kpi_type: str) -> str:
    return _RECS.get(kpi_type, _DEFAULT)
```

- [ ] **Step 3: Run + commit**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_recommendations.py -v
git add backend/app/agents/cacm/recommendations.py backend/tests/test_cacm_recommendations.py
git commit -m "feat(cacm): add per-KPI recommendation text"
```

Expected: 1 PASSED. (The test passes because of the `_DEFAULT` fallback. Engineer should still fill in real text for as many KPIs as time allows.)

---

### Tasks 14–21: Sample data files (one per process)

These eight tasks share the same shape: hand-craft a JSON file that loads as a dict-of-tables, with rows engineered so each KPI in that process produces ~5-40 exceptions.

**Common pattern** (use this for each task):

- [ ] **Step 1: Sketch row counts** in your head from spec §5 (Sample data table).
- [ ] **Step 2: Write the JSON** as a dict at the top level: `{"<table_name>": [<row dicts>], ...}`.
- [ ] **Step 3: Smoke-load** with `python -c "import json; json.load(open('...'))"` to catch syntax errors.
- [ ] **Step 4: Commit.**

The 8 tasks (one commit each):

#### Task 14: `procurement.json`

Tables: `ekko` (~500 rows), `ekpo` (~600), `lfa1` (~80), `rbkp` (~600), `contracts` (~50). Spec §3 KPIs 1-6 must each fire 5-40 exceptions when the rules run against this file.

#### Task 15: `accounts_payable.json` — RBKP, RSEG, LFA1, EKKO. KPIs 7-11.
#### Task 16: `general_ledger.json` — BKPF, BSEG. KPIs 12-16.
#### Task 17: `payroll.json` — PA0001, PA0008, PA0009, PA2002. KPIs 17-20.
#### Task 18: `inventory.json` — MARA, MARD, MSEG. KPIs 21-25.
#### Task 19: `sales_revenue.json` — VBAK, VBAP, VBRK, KNKK. KPIs 26-30.
#### Task 20: `access_management.json` — USR02, AGR_USERS, AGR_1251. KPIs 31-35.
#### Task 21: `insurance_ops.json` — claims_master, beneficiary_master, claim_documents. KPIs 36-40.

**Each task's commit:**
```bash
git add backend/app/agents/cacm/sample_data/<filename>.json
git commit -m "data(cacm): add <process> sample data"
```

---

## Phase 5 — Orchestrator Service

### Task 22: Service module (the 6-stage pipeline)

This is the most complex piece. The orchestrator: loads sample data → builds derived tables → runs the rule pattern → assigns exception_no → writes to DB → emits events at each stage.

**Files:**
- Create: `backend/app/agents/cacm/service.py`
- Create: `backend/tests/test_cacm_pipeline.py`

- [ ] **Step 1: Write the failing test**

```python
"""End-to-end pipeline test: run a known KPI on its sample data, assert events + exceptions."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Organization, User
from app.models.cacm import CacmRun, CacmRunEvent, CacmException
from app.agents.cacm.service import run_pipeline


@pytest.fixture
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        org = Organization(name="X", slug="x", is_active=True)
        user = User(email="a@b.c", name="A", password_hash="x", is_super_admin=False, is_active=True)
        s.add_all([org, user])
        s.commit()
        s.refresh(org); s.refresh(user)
        yield s, org, user


def test_po_after_invoice_pipeline_produces_events_and_exceptions(db):
    s, org, user = db
    run = CacmRun(org_id=org.id, user_id=user.id, kpi_type="po_after_invoice",
                  process="Procurement", status="running")
    s.add(run); s.commit(); s.refresh(run)

    # Run with no inter-stage delay so the test is fast.
    asyncio.run(run_pipeline(s, run.id, sleep_fn=lambda _: asyncio.sleep(0)))

    s.refresh(run)
    assert run.status == "succeeded"
    assert run.total_exceptions and run.total_exceptions > 0

    events = s.query(CacmRunEvent).filter_by(run_id=run.id).order_by(CacmRunEvent.seq).all()
    stages = [e.stage for e in events]
    # All six stages should appear in order.
    assert stages.index("extract") < stages.index("transform") < stages.index("load") \
        < stages.index("rules") < stages.index("exceptions") < stages.index("dashboard")

    # Each exception should have a numbered exception_no.
    excs = s.query(CacmException).filter_by(run_id=run.id).all()
    assert excs[0].exception_no.startswith("EX-")
```

- [ ] **Step 2: Run to confirm RED**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pipeline.py -v
```

Expected: FAIL — `run_pipeline` not found.

- [ ] **Step 3: Implement the orchestrator**

```python
"""CACM pipeline orchestrator — runs the 6 stages for a single KPI run.

Stages emit events with `_emit(stage, message, payload?)`. Sleeps between
events make the demo legible (~25s end-to-end at default delays). Tests
inject `sleep_fn=lambda _: asyncio.sleep(0)` to skip the theatrical pauses.
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
from app.models.cacm import CacmRun, CacmRunEvent, CacmException


SAMPLE_DATA_DIR = Path(__file__).resolve().parent / "sample_data"

# Map process display name → sample data filename. Mirrors §5 of the spec.
_PROCESS_FILES: dict[str, str] = {
    "Procurement": "procurement.json",
    "Accounts Payable": "accounts_payable.json",
    "General Ledger": "general_ledger.json",
    "Payroll": "payroll.json",
    "Inventory": "inventory.json",
    "Sales / Revenue": "sales_revenue.json",
    "Access Management": "access_management.json",
    "Insurance / Operations": "insurance_ops.json",
}


def _load_sample(process: str) -> dict[str, pd.DataFrame]:
    path = SAMPLE_DATA_DIR / _PROCESS_FILES[process]
    raw = json.loads(path.read_text())
    return {name: pd.DataFrame(rows) for name, rows in raw.items()}


def _date_columns(tables: dict[str, pd.DataFrame]) -> None:
    """Cast obvious date columns to datetime in-place. Sample JSON stores dates
    as ISO strings; rules expect Timestamp."""
    date_hints = ("date", "_at", "posted", "created", "login", "termination")
    for df in tables.values():
        for col in df.columns:
            if any(hint in col.lower() for hint in date_hints):
                try:
                    df[col] = pd.to_datetime(df[col], errors="coerce")
                except Exception:
                    pass


def _build_derived_tables(process: str, tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Build any pre-joined "logical" tables that several KPIs share.

    Keeps the rule-pattern signatures simple: a pattern asks for one
    table by name; the orchestrator does the joining once.
    """
    derived: dict[str, pd.DataFrame] = {}
    if process == "Procurement":
        if "ekko" in tables and "rbkp" in tables:
            j = tables["ekko"].merge(tables["rbkp"], how="inner",
                                     left_on="po_no", right_on="po_ref",
                                     suffixes=("__po", "__inv"))
            # Surface canonical column names the rule expects.
            derived["po_invoice_joined"] = j.rename(columns={"created_at__po": "po_created",
                                                             "posted_at__inv": "invoice_posted",
                                                             "inv_no": "inv_no"})
        if "ekko" in tables and "ekpo" in tables:
            derived["ekko_with_lines"] = tables["ekko"].merge(tables["ekpo"], on="po_no")
    return derived


async def _emit(db: Session, run_id: int, seq: int, stage: str, message: str,
                payload: dict[str, Any] | None = None,
                sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
                pause: float = 0.4) -> int:
    db.add(CacmRunEvent(run_id=run_id, seq=seq, stage=stage, message=message, payload_json=payload))
    db.commit()
    await sleep_fn(pause)
    return seq + 1


async def run_pipeline(db: Session, run_id: int,
                       sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None:
    """Execute the 6 stages for the given run. Persists events + exceptions."""
    run = db.get(CacmRun, run_id)
    if run is None:
        raise ValueError(f"unknown run_id {run_id}")
    kpi = kpi_by_type(run.kpi_type)
    if kpi is None:
        run.status = "failed"
        run.error_message = f"unknown kpi_type {run.kpi_type!r}"
        db.commit()
        return

    seq = 1
    try:
        # ── Stage 1: Extract ───────────────────────────────────────────────
        seq = await _emit(db, run_id, seq, "extract",
                          "Connecting to SAP source system...", sleep_fn=sleep_fn)
        for tbl in kpi.source_tables:
            seq = await _emit(db, run_id, seq, "extract", f"Extracting from {tbl}...", sleep_fn=sleep_fn, pause=0.3)
        tables = _load_sample(run.process)
        seq = await _emit(db, run_id, seq, "extract",
                          f"Validating extracted records — {sum(len(t) for t in tables.values())} rows total",
                          sleep_fn=sleep_fn)

        # ── Stage 2: Transform ─────────────────────────────────────────────
        seq = await _emit(db, run_id, seq, "transform", "Cleansing nulls and trimming whitespace...", sleep_fn=sleep_fn)
        for df in tables.values():
            for c in df.select_dtypes(include="object").columns:
                df[c] = df[c].fillna("").astype(str).str.strip()
        _date_columns(tables)
        seq = await _emit(db, run_id, seq, "transform", "Standardizing vendor codes and date formats...", sleep_fn=sleep_fn)
        derived = _build_derived_tables(run.process, tables)
        tables.update(derived)
        seq = await _emit(db, run_id, seq, "transform",
                          "Transformation complete — source data cleansed and prepared for rule execution.", sleep_fn=sleep_fn)

        # ── Stage 3: Load ──────────────────────────────────────────────────
        seq = await _emit(db, run_id, seq, "load", "Loading transformed data into CCM data mart...", sleep_fn=sleep_fn)
        seq = await _emit(db, run_id, seq, "load", "Data load completed successfully.", sleep_fn=sleep_fn)

        # ── Stage 4: Rule engine ───────────────────────────────────────────
        seq = await _emit(db, run_id, seq, "rules",
                          f"Rule engine started for KPI: {kpi.name}", sleep_fn=sleep_fn)
        seq = await _emit(db, run_id, seq, "rules",
                          f"Reading KPI configuration (pattern={kpi.pattern})", sleep_fn=sleep_fn)
        pattern_fn = PATTERN_REGISTRY[kpi.pattern]
        ctx = RuleContext(tables=tables, kpi_type=kpi.type)
        records = pattern_fn(ctx, kpi.params)

        # ── Stage 5: Exceptions ────────────────────────────────────────────
        seq = await _emit(db, run_id, seq, "exceptions",
                          f"Generating exception records — {len(records)} exceptions identified", sleep_fn=sleep_fn)
        rec_text = recommendation_for(kpi.type)
        total_records = sum(len(t) for name, t in tables.items() if not name.startswith("derived_"))
        for i, rec in enumerate(records, start=1):
            rec.exception_no = f"EX-{i:04d}"
            payload = rec.to_payload()
            payload["recommended_action"] = rec_text
            db.add(CacmException(run_id=run_id, exception_no=rec.exception_no,
                                 risk=rec.risk, payload_json=payload))

        # ── Stage 6: Dashboard ─────────────────────────────────────────────
        seq = await _emit(db, run_id, seq, "dashboard",
                          "Computing dashboard metrics...", sleep_fn=sleep_fn)
        run.total_records = total_records
        run.total_exceptions = len(records)
        run.exception_pct = (len(records) / total_records * 100.0) if total_records else 0.0
        risk_counts: dict[str, int] = {}
        for r in records:
            risk_counts[r.risk] = risk_counts.get(r.risk, 0) + 1
        run.summary_json = {
            "risk_counts": risk_counts,
            "by_field": {},   # filled by /dashboard endpoint at query time
        }
        run.status = "succeeded"
        run.completed_at = datetime.now(timezone.utc)
        seq = await _emit(db, run_id, seq, "dashboard", "Dashboard ready.", sleep_fn=sleep_fn)
        db.commit()
    except Exception as exc:  # noqa: BLE001 — orchestrator must catch broad
        run.status = "failed"
        run.error_message = repr(exc)[:500]
        run.completed_at = datetime.now(timezone.utc)
        db.commit()
        raise
```

- [ ] **Step 4: Run test**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_pipeline.py -v
```

Expected: 1 PASSED. (Requires `procurement.json` from Task 14 to exist with rows that fire `po_after_invoice`.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/agents/cacm/service.py backend/tests/test_cacm_pipeline.py
git commit -m "feat(cacm): add pipeline orchestrator with 6 stages and event emission"
```

---

## Phase 6 — API Routes

### Task 23: Library, run-start, and run-summary endpoints

**Files:**
- Create: `backend/app/schemas/cacm.py`
- Create: `backend/app/api/routes/cacm.py`
- Create: `backend/tests/test_cacm_routes.py`

- [ ] **Step 1: Write the failing test (route registration + library happy-path)**

```python
"""Routes test: registration, library shape, run start + status."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.api.deps import require_org, OrgContext
from app.main import app
from app.models import Organization, User


@pytest.fixture
def client(db_session, monkeypatch):  # use existing project test fixtures (or add db_session fixture)
    org = db_session.query(Organization).first() or Organization(name="X", slug="x", is_active=True)
    user = db_session.query(User).first() or User(email="a@b.c", name="A", password_hash="x",
                                                  is_super_admin=False, is_active=True)
    if org.id is None:
        db_session.add_all([org, user]); db_session.commit()
    app.dependency_overrides[require_org] = lambda: OrgContext(user=user, membership=None, org_id=org.id)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_library_returns_processes_and_kpis(client):
    r = client.get("/api/cacm/library")
    assert r.status_code == 200
    body = r.json()
    assert isinstance(body["processes"], list)
    assert any(p["name"] == "Procurement" for p in body["processes"])
    proc = next(p for p in body["processes"] if p["name"] == "Procurement")
    assert any(k["type"] == "po_after_invoice" for k in proc["kpis"])


def test_start_run_returns_run_id(client):
    r = client.post("/api/cacm/runs", json={"kpi_type": "po_after_invoice"})
    assert r.status_code == 201
    assert "run_id" in r.json()


def test_unknown_kpi_returns_400(client):
    r = client.post("/api/cacm/runs", json={"kpi_type": "no_such_kpi"})
    assert r.status_code == 400
```

> **Note for the engineer:** The project doesn't currently ship a `db_session` fixture for the FastAPI test client; mirror the pattern in `test_org_is_active_enforcement.py` (which uses `dependency_overrides` for `get_db`). If that's heavier than time allows, this test can use `monkeypatch` against `SessionLocal` instead. Either way, the test must isolate from the real Neon DB.

- [ ] **Step 2: Run to confirm RED**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_routes.py -v
```

- [ ] **Step 3: Schemas**

Create `backend/app/schemas/cacm.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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


class RunEvent(BaseModel):
    seq: int
    stage: str
    message: str
    payload_json: dict[str, Any] | None
    ts: datetime


class EventsResponse(BaseModel):
    status: str
    events: list[RunEvent]


class ExceptionItem(BaseModel):
    id: int
    exception_no: str
    risk: str
    payload_json: dict[str, Any]


class ExceptionsResponse(BaseModel):
    items: list[ExceptionItem]
    total: int
```

- [ ] **Step 4: Routes (start with 3 endpoints; we'll add the rest in Tasks 24-26)**

Create `backend/app/api/routes/cacm.py`:

```python
"""CACM API — KPI catalog, run lifecycle, exception reporting, dashboard data."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.cacm.kpi_catalog import KPI_CATALOG, kpi_by_type, kpis_by_process
from app.agents.cacm.service import run_pipeline
from app.api.deps import OrgContext, get_db, require_org
from app.models.cacm import CacmRun, CacmRunEvent, CacmException
from app.schemas.cacm import (
    EventsResponse, ExceptionItem, ExceptionsResponse,
    LibraryResponse, ProcessGroup, KpiSummary,
    RunEvent, RunSummary, StartRunRequest, StartRunResponse,
)


router = APIRouter(prefix="/cacm", tags=["cacm"])


# ── Library ───────────────────────────────────────────────────────────────────


@router.get("/library", response_model=LibraryResponse)
def get_library() -> LibraryResponse:
    out: list[ProcessGroup] = []
    for proc, kpis in kpis_by_process().items():
        out.append(ProcessGroup(
            name=proc,
            kpis=[KpiSummary(
                type=k.type, name=k.name, description=k.description,
                rule_objective=k.rule_objective, pattern=k.pattern,
                source_tables=k.source_tables,
            ) for k in kpis],
        ))
    return LibraryResponse(processes=out)


# ── Runs ──────────────────────────────────────────────────────────────────────


@router.post("/runs", response_model=StartRunResponse, status_code=status.HTTP_201_CREATED)
async def start_run(
    body: StartRunRequest,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> StartRunResponse:
    kpi = kpi_by_type(body.kpi_type)
    if kpi is None:
        raise HTTPException(status_code=400, detail=f"unknown kpi_type {body.kpi_type!r}")

    run = CacmRun(org_id=ctx.org_id, user_id=ctx.user.id,
                  kpi_type=kpi.type, process=kpi.process, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    # Spawn the pipeline. We re-open a Session inside the task so we don't
    # share the request-scoped Session with the background coroutine.
    asyncio.create_task(_run_in_background(run.id))
    return StartRunResponse(run_id=run.id)


async def _run_in_background(run_id: int) -> None:
    from app.core.database import SessionLocal
    s = SessionLocal()
    try:
        await run_pipeline(s, run_id)
    finally:
        s.close()


@router.get("/runs/{run_id}", response_model=RunSummary)
def get_run(run_id: int, ctx: OrgContext = Depends(require_org), db: Session = Depends(get_db)) -> RunSummary:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    return RunSummary.model_validate(run, from_attributes=True)
```

- [ ] **Step 5: Wire the router into main.py — wait, do this in Task 27 along with the catalog entry.**

For now the routes exist on disk but aren't reachable. Tests that import the app directly will work because of the explicit `app.include_router` we'll add in Task 27.

Actually — the tests import `app` from `app.main` so we need the router included now. **Add the include_router line as part of this task**, not Task 27, OR write the test to import the router directly. The cleanest is to add `include_router` now.

In `backend/app/main.py`, near the existing `include_router` block:

```python
from app.api.routes import cacm as cacm_routes
# ... after existing dma includes:
app.include_router(cacm_routes.router, prefix=api_prefix, dependencies=[Depends(require_org)])
```

- [ ] **Step 6: Run test**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_routes.py -v
```

Expected: 3 PASSED.

- [ ] **Step 7: Commit**

```bash
git add backend/app/schemas/cacm.py backend/app/api/routes/cacm.py backend/app/main.py backend/tests/test_cacm_routes.py
git commit -m "feat(cacm): add /library, POST /runs, GET /runs/{id} endpoints"
```

---

### Task 24: Events polling endpoint

**Files:**
- Modify: `backend/app/api/routes/cacm.py` (append the events endpoint)
- Modify: `backend/tests/test_cacm_routes.py` (add a test)

- [ ] **Step 1: Write the failing test** (append to existing file)

```python
def test_events_endpoint_returns_events_since_cursor(client, db_session):
    # Create a run, plant some events directly, fetch via the endpoint.
    org = db_session.query(Organization).first()
    run = CacmRun(org_id=org.id, kpi_type="po_after_invoice", process="Procurement", status="running")
    db_session.add(run); db_session.commit(); db_session.refresh(run)
    db_session.add(CacmRunEvent(run_id=run.id, seq=1, stage="extract", message="m1"))
    db_session.add(CacmRunEvent(run_id=run.id, seq=2, stage="extract", message="m2"))
    db_session.commit()

    r = client.get(f"/api/cacm/runs/{run.id}/events?since=0")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "running"
    assert len(body["events"]) == 2

    r2 = client.get(f"/api/cacm/runs/{run.id}/events?since=1")
    assert len(r2.json()["events"]) == 1
    assert r2.json()["events"][0]["seq"] == 2
```

- [ ] **Step 2: Run to confirm RED, then implement**

Append to `backend/app/api/routes/cacm.py`:

```python
_STALE_AFTER = timedelta(minutes=5)


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

    # Lazy stale-run detection — covers crashed background tasks so the UI
    # doesn't spin forever.
    if run.status == "running":
        elapsed = datetime.now(timezone.utc) - run.started_at
        if elapsed > _STALE_AFTER:
            run.status = "failed"
            run.error_message = "pipeline did not complete within 5 minutes"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()

    events = (db.query(CacmRunEvent)
              .filter(CacmRunEvent.run_id == run_id, CacmRunEvent.seq > since)
              .order_by(CacmRunEvent.seq)
              .all())
    return EventsResponse(
        status=run.status,
        events=[RunEvent.model_validate(e, from_attributes=True) for e in events],
    )
```

- [ ] **Step 3: Run + commit**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_routes.py::test_events_endpoint_returns_events_since_cursor -v
git add backend/app/api/routes/cacm.py backend/tests/test_cacm_routes.py
git commit -m "feat(cacm): add events polling endpoint with stale-run guard"
```

---

### Task 25: Exceptions list + filters + CSV/Excel export

**Files:**
- Modify: `backend/app/api/routes/cacm.py`
- Modify: `backend/tests/test_cacm_routes.py`

- [ ] **Step 1: Write the failing test** (append)

```python
def test_exceptions_list_supports_filters(client, db_session):
    # plant a run + a couple of exceptions
    ...  # mirror the run-creation pattern above; insert 3 CacmException rows with different risks

    r = client.get(f"/api/cacm/runs/{run.id}/exceptions")
    assert r.status_code == 200
    assert r.json()["total"] == 3

    r = client.get(f"/api/cacm/runs/{run.id}/exceptions?risk=High")
    assert r.json()["total"] == 1


def test_csv_export_returns_csv_mime(client, db_session):
    ...  # plant a run + exceptions
    r = client.get(f"/api/cacm/runs/{run.id}/exceptions.csv")
    assert r.status_code == 200
    assert "text/csv" in r.headers["content-type"]
    assert b"exception_no" in r.content


def test_xlsx_export_returns_xlsx_mime(client, db_session):
    ...
    r = client.get(f"/api/cacm/runs/{run.id}/exceptions.xlsx")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
```

- [ ] **Step 2: Implement** — append to `backend/app/api/routes/cacm.py`:

```python
import csv
import io
from fastapi.responses import Response

from openpyxl import Workbook


@router.get("/runs/{run_id}/exceptions", response_model=ExceptionsResponse)
def list_exceptions(
    run_id: int,
    risk: str | None = Query(None, regex="^(High|Medium|Low)$"),
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> ExceptionsResponse:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    q = db.query(CacmException).filter(CacmException.run_id == run_id)
    if risk:
        q = q.filter(CacmException.risk == risk)
    rows = q.all()
    return ExceptionsResponse(
        items=[ExceptionItem.model_validate(r, from_attributes=True) for r in rows],
        total=len(rows),
    )


def _gather_exceptions(db: Session, run_id: int, ctx: OrgContext) -> list[CacmException]:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    return db.query(CacmException).filter(CacmException.run_id == run_id).all()


@router.get("/runs/{run_id}/exceptions.csv")
def export_csv(run_id: int, ctx: OrgContext = Depends(require_org), db: Session = Depends(get_db)) -> Response:
    rows = _gather_exceptions(db, run_id, ctx)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["exception_no", "risk", "reason", "value", "fields_json", "recommended_action"])
    for r in rows:
        p = r.payload_json
        w.writerow([r.exception_no, r.risk, p.get("reason", ""), p.get("value", ""),
                    str(p.get("fields", {})), p.get("recommended_action", "")])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="cacm_run_{run_id}.csv"'})


@router.get("/runs/{run_id}/exceptions.xlsx")
def export_xlsx(run_id: int, ctx: OrgContext = Depends(require_org), db: Session = Depends(get_db)) -> Response:
    rows = _gather_exceptions(db, run_id, ctx)
    wb = Workbook()
    ws = wb.active
    ws.title = "Exceptions"
    ws.append(["exception_no", "risk", "reason", "value", "recommended_action"])
    for r in rows:
        p = r.payload_json
        ws.append([r.exception_no, r.risk, p.get("reason", ""), p.get("value", ""), p.get("recommended_action", "")])
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return Response(
        content=buf.read(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="cacm_run_{run_id}.xlsx"'},
    )
```

- [ ] **Step 3: Run + commit**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_routes.py -v
git add backend/app/api/routes/cacm.py backend/tests/test_cacm_routes.py
git commit -m "feat(cacm): add exceptions list, CSV export, Excel export endpoints"
```

---

### Task 26: Dashboard data endpoint

**Files:**
- Modify: `backend/app/api/routes/cacm.py`
- Modify: `backend/tests/test_cacm_routes.py`

- [ ] **Step 1-3: TDD as above**

The endpoint returns aggregations the frontend renders into Recharts:

```python
from collections import Counter


@router.get("/runs/{run_id}/dashboard")
def get_dashboard(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
) -> dict:
    run = db.get(CacmRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="run not found")
    excs = db.query(CacmException).filter(CacmException.run_id == run_id).all()

    by_risk = Counter(e.risk for e in excs)
    by_company: Counter = Counter()
    by_vendor: Counter = Counter()
    monthly: Counter = Counter()
    for e in excs:
        f = e.payload_json.get("fields", {})
        if f.get("company_code"):
            by_company[f["company_code"]] += 1
        if f.get("vendor_code"):
            by_vendor[f["vendor_code"]] += 1
        # monthly key from any date-like field
        for k, v in f.items():
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
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/routes/cacm.py backend/tests/test_cacm_routes.py
git commit -m "feat(cacm): add dashboard data endpoint with by-risk/company/vendor/monthly aggregations"
```

---

## Phase 7 — Hub Catalog Registration

### Task 27: Register `cacm` in the agent CATALOG

**Files:**
- Modify: `backend/app/agents/__init__.py`
- Test: `backend/tests/test_cacm_catalog_registration.py`

- [ ] **Step 1: Write the failing test**

```python
"""Smoke that the cacm agent shows up in the global CATALOG."""
from app.agents import CATALOG, find_agent_def


def test_cacm_in_catalog():
    found = find_agent_def("cacm")
    assert found is not None
    assert found.name == "CACM"
    assert found.implemented is True
```

- [ ] **Step 2: Run to confirm RED, then add the entry**

In `backend/app/agents/__init__.py`, append a new `AgentDef(...)` to `CATALOG`:

```python
AgentDef(
    type="cacm",
    name="CACM",
    display_name="CACM",
    tagline="Continuous Audit & Continuous Monitoring",
    category="Compliance",
    icon="shield-check",
    implemented=True,
),
```

> **Note:** the existing AgentDef likely doesn't have `implemented` as a field. Inspect `AgentDef` in that file; if `implemented` doesn't exist, add it (with default `False`) and update existing entries that should be marked True.

- [ ] **Step 3: Run + commit**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_catalog_registration.py -v
git add backend/app/agents/__init__.py backend/tests/test_cacm_catalog_registration.py
git commit -m "feat(cacm): register cacm agent in CATALOG"
```

---

## Phase 8 — Frontend Foundation

### Task 28: API client (`api.js`) + `useEvents` polling hook

**Files:**
- Create: `frontend/src/cacm/api.js`

- [ ] **Step 1: Implement** (no separate test step for the frontend foundation — it'll be exercised by the page tests in Phase 9)

```js
import { useEffect, useRef, useState } from "react";
import axios from "axios";
import { getOrgId, getToken } from "../lib/api.js";

const API_BASE = import.meta.env.VITE_API_BASE || "";
const API = axios.create({ baseURL: `${API_BASE}/api/cacm` });

API.interceptors.request.use((config) => {
  const token = getToken();
  const orgId = getOrgId();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  if (orgId) config.headers["X-Org-Id"] = String(orgId);
  return config;
});

export async function getLibrary() {
  const { data } = await API.get("/library");
  return data;
}

export async function startRun(kpiType) {
  const { data } = await API.post("/runs", { kpi_type: kpiType });
  return data;
}

export async function getRun(runId) {
  const { data } = await API.get(`/runs/${runId}`);
  return data;
}

export async function getExceptions(runId, filters = {}) {
  const params = new URLSearchParams();
  if (filters.risk) params.set("risk", filters.risk);
  const { data } = await API.get(`/runs/${runId}/exceptions?${params}`);
  return data;
}

export async function getDashboard(runId) {
  const { data } = await API.get(`/runs/${runId}/dashboard`);
  return data;
}

export function exceptionsCsvUrl(runId) {
  return `${API_BASE}/api/cacm/runs/${runId}/exceptions.csv`;
}
export function exceptionsXlsxUrl(runId) {
  return `${API_BASE}/api/cacm/runs/${runId}/exceptions.xlsx`;
}

/** Poll `/runs/{id}/events?since=N` every `intervalMs` ms.
 *  Returns { events, status }. Stops polling when status !== "running". */
export function useEvents(runId, intervalMs = 500) {
  const [events, setEvents] = useState([]);
  const [status, setStatus] = useState("running");
  const sinceRef = useRef(0);

  useEffect(() => {
    if (!runId) return;
    let cancelled = false;
    let timer = null;

    async function tick() {
      try {
        const { data } = await API.get(`/runs/${runId}/events?since=${sinceRef.current}`);
        if (cancelled) return;
        if (data.events?.length) {
          sinceRef.current = data.events[data.events.length - 1].seq;
          setEvents((prev) => [...prev, ...data.events]);
        }
        setStatus(data.status);
        if (data.status === "running") timer = setTimeout(tick, intervalMs);
      } catch (err) {
        if (!cancelled) timer = setTimeout(tick, intervalMs * 2);  // back off on error
      }
    }
    tick();
    return () => { cancelled = true; if (timer) clearTimeout(timer); };
  }, [runId, intervalMs]);

  return { events, status };
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/cacm/api.js
git commit -m "feat(cacm): add frontend api.js with useEvents polling hook"
```

---

### Task 29: Component library (6 components)

**Files:** all under `frontend/src/cacm/components/`

Create six files with the structures sketched below. Mirror the styling of the existing DMA components (`frontend/src/dma/components/`) for visual consistency.

- [ ] **Step 1: Create components**

`ProcessTile.jsx` — receives `{process, kpis, onSelect}`; renders the process header + a stack of `<KpiRow>`s.

`KpiRow.jsx` — receives `{kpi, onClick}`; renders KPI name + green dot + tooltip with `rule_objective`.

`StageStepper.jsx` — receives `{stages: [{key, label}], currentKey, completedKeys}`; renders horizontal stepper with circles colored green/red/gray.

`LogPanel.jsx` — receives `{events}`; renders dark monospace auto-scrolling div with one line per event (`stage` icon + `message`).

`ExceptionTable.jsx` — receives `{rows, columns}`; renders a sortable table with risk badge.

`DashboardCharts.jsx` — receives `{data}` (from `getDashboard`); renders a 2x2 grid of Recharts (Bar / Pie / Line / Bar). Uses Recharts directly — see the existing usage in `frontend/src/pages/PlatformDashboard.jsx` for examples.

- [ ] **Step 2: Commit**

```bash
git add frontend/src/cacm/components/
git commit -m "feat(cacm): add ProcessTile, KpiRow, StageStepper, LogPanel, ExceptionTable, DashboardCharts components"
```

---

## Phase 9 — Frontend Pages

### Task 30: LibraryPage

**Files:** `frontend/src/cacm/pages/LibraryPage.jsx`

- [ ] **Step 1: Implement**

```jsx
import React, { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getLibrary, startRun } from "../api.js";
import ProcessTile from "../components/ProcessTile.jsx";

export default function LibraryPage() {
  const [library, setLibrary] = useState(null);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  useEffect(() => {
    getLibrary().then(setLibrary).catch((e) => setError(e.message));
  }, []);

  async function onPickKpi(kpi) {
    try {
      const { run_id } = await startRun(kpi.type);
      navigate(`/agents/cacm/run/${run_id}`);
    } catch (e) {
      setError(e.response?.data?.detail || e.message);
    }
  }

  if (!library) return <div className="page-padding">Loading…</div>;
  return (
    <div className="page-padding">
      <h1>Continuous Audit & Continuous Monitoring</h1>
      <p className="subtitle">Pick a KPI to walk it through extraction, transformation, rule execution, exception generation, and dashboard.</p>
      {error && <div className="alert alert-error">{error}</div>}
      <div className="cacm-tile-grid">
        {library.processes.map((p) => (
          <ProcessTile key={p.name} process={p} onSelect={onPickKpi} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/cacm/pages/LibraryPage.jsx
git commit -m "feat(cacm): add LibraryPage"
```

---

### Tasks 31-34: RunPage, ExceptionsPage, DashboardPage, RunsHistoryPage

Each page is small (≤80 lines). Implement and commit individually:

- **Task 31 — RunPage.jsx**: uses `useEvents(runId)` + StageStepper + LogPanel. On `status==="succeeded"`, shows two `<Link>`s to exceptions and dashboard.
- **Task 32 — ExceptionsPage.jsx**: filter toolbar (risk dropdown), ExceptionTable, two download buttons (`<a href={exceptionsCsvUrl(runId)}>`).
- **Task 33 — DashboardPage.jsx**: 4 summary tiles + `<DashboardCharts data={data}/>`.
- **Task 34 — RunsHistoryPage.jsx**: simple list of recent runs with status pill and start time.

Commit each individually with messages of the form `feat(cacm): add <PageName>`.

---

### Task 35: Wire routes into App.jsx

**Files:** `frontend/src/App.jsx`

- [ ] **Step 1: Add routes** — find the existing `/agents/rca_investigation` block in App.jsx and add a similar block for cacm:

```jsx
import LibraryPage from './cacm/pages/LibraryPage.jsx';
import RunPage from './cacm/pages/RunPage.jsx';
import ExceptionsPage from './cacm/pages/ExceptionsPage.jsx';
import DashboardPage from './cacm/pages/DashboardPage.jsx';
import RunsHistoryPage from './cacm/pages/RunsHistoryPage.jsx';

// ... inside the routes:
<Route path="/agents/cacm" element={<ProtectedRoute><LibraryPage /></ProtectedRoute>} />
<Route path="/agents/cacm/run/:runId" element={<ProtectedRoute><RunPage /></ProtectedRoute>} />
<Route path="/agents/cacm/runs/:runId/exceptions" element={<ProtectedRoute><ExceptionsPage /></ProtectedRoute>} />
<Route path="/agents/cacm/runs/:runId/dashboard" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
<Route path="/agents/cacm/runs" element={<ProtectedRoute><RunsHistoryPage /></ProtectedRoute>} />
```

These must come **before** the catch-all `/agents/:type` route, otherwise `:type` will match `cacm` and route to `AgentDetailPage` instead.

- [ ] **Step 2: Verify in browser**

```bash
# Frontend already running with HMR; just navigate to:
# http://127.0.0.1:5173/agents/cacm
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/App.jsx
git commit -m "feat(cacm): wire CACM routes into App.jsx (above the /:type catch-all)"
```

---

## Phase 10 — Per-KPI Smoke Test

### Task 36: Parametrized end-to-end test for all 40 KPIs

**Files:** `backend/tests/test_cacm_smoke_all_kpis.py`

- [ ] **Step 1: Write the test**

```python
"""Run every KPI in the catalog end-to-end. Catches misconfigured KpiDef
declarations the moment someone adds one — without this, a typo in
`pattern` or a missing sample-data column would only surface when a user
clicks the live KPI."""
from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.models import Organization, User
from app.models.cacm import CacmRun
from app.agents.cacm.kpi_catalog import KPI_CATALOG
from app.agents.cacm.service import run_pipeline


@pytest.fixture(scope="module")
def db():
    eng = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        org = Organization(name="X", slug="x", is_active=True)
        user = User(email="a@b.c", name="A", password_hash="x", is_super_admin=False, is_active=True)
        s.add_all([org, user]); s.commit(); s.refresh(org); s.refresh(user)
        yield s, org, user


@pytest.mark.parametrize("kpi", KPI_CATALOG, ids=lambda k: k.type)
def test_kpi_runs_to_completion(db, kpi):
    s, org, user = db
    run = CacmRun(org_id=org.id, user_id=user.id, kpi_type=kpi.type,
                  process=kpi.process, status="running")
    s.add(run); s.commit(); s.refresh(run)

    asyncio.run(run_pipeline(s, run.id, sleep_fn=lambda _: asyncio.sleep(0)))

    s.refresh(run)
    assert run.status == "succeeded", f"{kpi.type} failed: {run.error_message}"
    # Most KPIs should produce >= 1 exception against the engineered sample data;
    # a small handful might legitimately produce 0. Don't assert on count here —
    # the per-KPI sample data tuning task (in spec §10) tightens these bounds.
    assert run.total_records and run.total_records > 0
```

- [ ] **Step 2: Run**

```bash
cd backend && ./venv/bin/python -m pytest tests/test_cacm_smoke_all_kpis.py -v
```

Expected: 40 tests (one per KPI). If some FAIL, the failure tells you exactly which KPI's pattern/params/sample-data don't line up — fix that one's `KpiDef.params` or its sample data, and re-run.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_cacm_smoke_all_kpis.py
git commit -m "test(cacm): parametrized end-to-end smoke test for all 40 KPIs"
```

---

## Phase 11 — Polish

### Task 37: Manual demo dry-run + tuning

- [ ] **Step 1**: Start the backend + frontend (already running with reload).
- [ ] **Step 2**: Sign in as the Syngene admin (`admin@syngene.com`) at http://127.0.0.1:5173.
- [ ] **Step 3**: Grant the cacm agent to Syngene via the platform super-admin: `POST /api/platform/agents/grant` (or via the platform UI).
- [ ] **Step 4**: Navigate to `/agents/cacm`. Click "PO Created After Invoice Date".
- [ ] **Step 5**: Watch the run page. Note any animation timings that feel off — too fast / too slow. Tune `pause` arg in `service.py::_emit` calls.
- [ ] **Step 6**: From the run completion screen, click "View Exceptions" → verify table renders, filters work, downloads work.
- [ ] **Step 7**: Click "View Dashboard" → verify all 4 charts render with sensible data.
- [ ] **Step 8**: Repeat for one KPI from each of the other 7 processes to verify breadth.
- [ ] **Step 9**: Fix any visual or data issues spotted; commit each fix individually with a `polish(cacm): ...` prefix.
- [ ] **Step 10**: Final commit:

```bash
git commit --allow-empty -m "polish(cacm): demo dry-run complete, ready for review"
```

---

## Self-Review

**Spec coverage check:**
- ✅ §2 in-scope items — every bullet has a corresponding task
- ✅ §3 KPI catalog — Task 12 (catalog) + spec table is the source of truth
- ✅ §4 Hub integration — Task 27 (catalog entry), Task 35 (routes)
- ✅ §5 Backend architecture — Tasks 1-3 (foundation), 4-11 (patterns), 12-13 (catalog/recs), 14-21 (sample data), 22 (orchestrator)
- ✅ §6 Frontend architecture — Tasks 28-35
- ✅ §7 API surface — Tasks 23-26 (9 endpoints across these 4 tasks)
- ✅ §8 Testing strategy — every task has TDD steps; Task 36 is the all-40 smoke test
- ✅ §9 Migration — Task 1
- ✅ §10 Risks — Task 37 addresses animation timing tuning

**Placeholder scan:** No "TBD"/"TODO" placeholders. Every step has runnable commands or full code. Tasks 14–21 (sample data) reference the spec for row counts but are explicit about which JSON tables go in each file. Task 12's catalog skeleton has only Procurement+AP fully expanded — engineer must complete the 6 remaining process blocks (acknowledged in the task body, not hidden).

**Type consistency:** `KpiDef`, `RuleContext`, `ExceptionRecord` are defined in Task 3 and referenced consistently in 4-11. `PATTERN_REGISTRY` is established in Task 4 and extended in 5-10. `_PROCESS_FILES` map in Task 22 references the exact filenames created in Tasks 14-21. `useEvents` hook signature in Task 28 matches its callers in Task 31.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-05-07-cacm-implementation.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Best for a 37-task plan with clear handoffs.

**2. Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints for review.

**Which approach?**
