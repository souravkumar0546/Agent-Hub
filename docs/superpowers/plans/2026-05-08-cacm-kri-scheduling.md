# CACM KRI-Level Run & Schedule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-KRI Run and Schedule controls to the CACM Process Detail page, with backend persistence (`cacm_schedules` table), CRUD routes, and a single-process asyncio scheduler that fires runs at the configured cadence. Eye-icon button on each KRI shows view/edit/delete modal when a schedule exists. Remove the misleading "Schedule whole process" button from the run wizard.

**Architecture:** New SQLAlchemy model `CacmSchedule` + Alembic migration. Pydantic schemas + four routes added to `app/api/routes/cacm.py`. A pure helper `compute_next_run_at(frequency, time_of_day, now)` lives in `app/agents/cacm/schedule_math.py`. A background asyncio loop started by FastAPI lifespan polls every 60 s, creates `CacmRun` rows for due schedules, kicks off `_run_in_background`, and advances `next_run_at`. Frontend gets a `ScheduleModal` and ProcessDetailPage rows split into name + Run + Schedule + (eye if scheduled).

**Tech Stack:** FastAPI · SQLAlchemy 2.x · Alembic · Pydantic v2 · React 18 · axios · pytest

**Spec:** [docs/superpowers/specs/2026-05-08-cacm-kri-scheduling-design.md](../specs/2026-05-08-cacm-kri-scheduling-design.md)

**User preference:** Do NOT run `git add` or `git commit`. The user handles git themselves. The "Commit" step in each task is reduced to a manual checkpoint instead of a shell command.

---

## File map

**Created:**
- `backend/app/agents/cacm/schedule_math.py` — pure helper for `compute_next_run_at`
- `backend/alembic/versions/<rev>_add_cacm_schedules.py` — migration
- `backend/app/agents/cacm/scheduler.py` — async loop + tick
- `backend/tests/test_cacm_schedule_math.py`
- `backend/tests/test_cacm_schedule_models.py`
- `backend/tests/test_cacm_schedule_routes.py`
- `backend/tests/test_cacm_schedule_scheduler.py`
- `frontend/src/cacm/components/ScheduleModal.jsx`

**Modified:**
- `backend/app/models/cacm.py` — add `CacmSchedule` model
- `backend/app/models/__init__.py` — re-export `CacmSchedule`
- `backend/app/schemas/cacm.py` — add `ScheduleCreate`, `ScheduleUpdate`, `ScheduleSummary`, `SchedulesResponse`
- `backend/app/api/routes/cacm.py` — add four `/schedules` routes
- `backend/app/main.py` — start/stop scheduler in `lifespan`
- `frontend/src/cacm/api.js` — add `createSchedule`, `listSchedules`, `updateSchedule`, `deleteSchedule`
- `frontend/src/cacm/pages/ProcessDetailPage.jsx` — three-button KRI row + eye icon + load schedules
- `frontend/src/cacm/pages/RunPage.jsx` — remove `Schedule whole process` button + `onScheduleAll` plumbing
- `frontend/src/cacm/styles.css` — add `.cacm-kri-row`, `.cacm-kri-actions`, `.cacm-kri-eye`, `.cacm-schedule-modal*` styles

---

## Task 1: schedule_math helper (pure function, fast TDD)

**Files:**
- Create: `backend/app/agents/cacm/schedule_math.py`
- Test: `backend/tests/test_cacm_schedule_math.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_cacm_schedule_math.py
"""Pure-function tests for schedule next-run math."""
from datetime import datetime, timezone

import pytest

from app.agents.cacm.schedule_math import compute_next_run_at


# Helper: build a UTC datetime from naive components.
def _utc(y, mo, d, h=0, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=timezone.utc)


def test_daily_rolls_to_next_day_when_time_already_passed():
    # now = 2026-05-08 10:00 UTC, time_of_day "09:00" → next is 2026-05-09 09:00.
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("daily", "09:00", now=now)
    assert nxt == _utc(2026, 5, 9, 9, 0)


def test_daily_uses_today_when_time_not_yet_passed():
    now = _utc(2026, 5, 8, 8, 0)
    nxt = compute_next_run_at("daily", "09:00", now=now)
    assert nxt == _utc(2026, 5, 8, 9, 0)


def test_weekly_advances_seven_days():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("weekly", "09:00", now=now)
    assert nxt == _utc(2026, 5, 15, 9, 0)


def test_monthly_advances_one_calendar_month():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("monthly", "09:00", now=now)
    assert nxt == _utc(2026, 6, 8, 9, 0)


def test_monthly_clamps_to_last_day():
    # Anchor on Jan 31 → Feb has 28 days in 2026 → result is Feb 28.
    now = _utc(2026, 1, 31, 10, 0)
    nxt = compute_next_run_at("monthly", "09:00", now=now)
    assert nxt == _utc(2026, 2, 28, 9, 0)


def test_quarterly_adds_three_months():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("quarterly", "09:00", now=now)
    assert nxt == _utc(2026, 8, 8, 9, 0)


def test_half_yearly_adds_six_months():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("half_yearly", "09:00", now=now)
    assert nxt == _utc(2026, 11, 8, 9, 0)


def test_annually_adds_one_year():
    now = _utc(2026, 5, 8, 10, 0)
    nxt = compute_next_run_at("annually", "09:00", now=now)
    assert nxt == _utc(2027, 5, 8, 9, 0)


def test_annually_leap_day_clamps_to_feb28():
    now = _utc(2024, 2, 29, 10, 0)
    nxt = compute_next_run_at("annually", "09:00", now=now)
    assert nxt == _utc(2025, 2, 28, 9, 0)


def test_unknown_frequency_raises_value_error():
    now = _utc(2026, 5, 8, 10, 0)
    with pytest.raises(ValueError):
        compute_next_run_at("hourly", "09:00", now=now)


def test_invalid_time_of_day_raises_value_error():
    now = _utc(2026, 5, 8, 10, 0)
    with pytest.raises(ValueError):
        compute_next_run_at("daily", "9am", now=now)


def test_naive_now_is_rejected():
    # We require a tz-aware UTC `now`; naive input is a programmer error.
    with pytest.raises(ValueError):
        compute_next_run_at("daily", "09:00", now=datetime(2026, 5, 8, 10, 0))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_math.py -v`
Expected: ImportError on `from app.agents.cacm.schedule_math import compute_next_run_at`.

- [ ] **Step 3: Write minimal implementation**

```python
# backend/app/agents/cacm/schedule_math.py
"""Pure helpers for CACM schedule math.

Schedules use a "relative-to-creation" anchor — there is no day-of-week or
day-of-month picker in the UI. `compute_next_run_at` therefore takes only
`(frequency, time_of_day, now)` and returns the next UTC datetime when the
schedule should fire.

`now` MUST be timezone-aware (UTC). The returned value preserves the
day-of-month from `now` for monthly+ frequencies, clamping to the last
valid day of the target month (e.g. Jan 31 + 1 month → Feb 28/29).
"""
from __future__ import annotations

import calendar
from datetime import datetime, timedelta, timezone
from typing import Final


_FREQUENCIES: Final[set[str]] = {
    "daily", "weekly", "monthly", "quarterly", "half_yearly", "annually",
}


def _parse_time(s: str) -> tuple[int, int]:
    """Parse a strict HH:MM string. Raises ValueError on bad input."""
    if not isinstance(s, str) or len(s) != 5 or s[2] != ":":
        raise ValueError(f"time_of_day must be HH:MM, got {s!r}")
    try:
        hh = int(s[:2])
        mm = int(s[3:])
    except ValueError as e:
        raise ValueError(f"time_of_day must be HH:MM digits, got {s!r}") from e
    if not (0 <= hh <= 23 and 0 <= mm <= 59):
        raise ValueError(f"time_of_day out of range, got {s!r}")
    return hh, mm


def _add_months(dt: datetime, months: int) -> datetime:
    """Add calendar months, clamping day to the last day of the target month."""
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(dt.day, last_day)
    return dt.replace(year=year, month=month, day=day)


def compute_next_run_at(
    frequency: str,
    time_of_day: str,
    *,
    now: datetime,
) -> datetime:
    """Return the next UTC datetime at which a schedule should fire.

    Algorithm:
      1. anchor = today @ time_of_day in UTC.
      2. If anchor <= now, advance one period.
      3. Return anchor.

    Raises ValueError on an unknown frequency, malformed time_of_day, or a
    naive `now`.
    """
    if frequency not in _FREQUENCIES:
        raise ValueError(f"unknown frequency {frequency!r}")
    if now.tzinfo is None:
        raise ValueError("now must be timezone-aware (UTC)")
    hh, mm = _parse_time(time_of_day)

    anchor = now.astimezone(timezone.utc).replace(
        hour=hh, minute=mm, second=0, microsecond=0,
    )

    if anchor > now:
        return anchor

    if frequency == "daily":
        return anchor + timedelta(days=1)
    if frequency == "weekly":
        return anchor + timedelta(days=7)
    if frequency == "monthly":
        return _add_months(anchor, 1)
    if frequency == "quarterly":
        return _add_months(anchor, 3)
    if frequency == "half_yearly":
        return _add_months(anchor, 6)
    # annually
    return _add_months(anchor, 12)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_math.py -v`
Expected: 12 passed.

- [ ] **Step 5: Checkpoint**

Stop here for review. The user will stage and commit when ready.

---

## Task 2: `CacmSchedule` SQLAlchemy model + re-export

**Files:**
- Modify: `backend/app/models/cacm.py`
- Modify: `backend/app/models/__init__.py`
- Test: `backend/tests/test_cacm_schedule_models.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_cacm_schedule_models.py
"""Persistence tests for CacmSchedule — round-trip + unique constraint."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models import CacmSchedule, Organization, User


@pytest.fixture
def session():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    LocalSession = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    with LocalSession() as s:
        org = Organization(name="X", slug="x", is_active=True)
        user = User(email="a@b.c", name="A", password_hash="x",
                    is_super_admin=False, is_active=True)
        s.add_all([org, user])
        s.commit()
        s.refresh(org)
        s.refresh(user)
        yield s, org, user


def _row(org, user, **overrides):
    base = dict(
        org_id=org.id,
        user_id=user.id,
        process_key="procurement_to_payment",
        kri_name="PO issued after invoice date (retroactive approvals)",
        kpi_type="po_after_invoice",
        frequency="daily",
        time_of_day="09:00",
        next_run_at=datetime(2026, 5, 9, 9, 0, tzinfo=timezone.utc),
        is_active=True,
    )
    base.update(overrides)
    return CacmSchedule(**base)


def test_round_trip(session):
    s, org, user = session
    s.add(_row(org, user))
    s.commit()
    out = s.query(CacmSchedule).one()
    assert out.process_key == "procurement_to_payment"
    assert out.frequency == "daily"
    assert out.time_of_day == "09:00"
    assert out.is_active is True
    assert out.last_run_id is None


def test_unique_per_org_process_kri(session):
    s, org, user = session
    s.add(_row(org, user))
    s.commit()
    s.add(_row(org, user, frequency="weekly"))
    with pytest.raises(IntegrityError):
        s.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_models.py -v`
Expected: ImportError on `CacmSchedule`.

- [ ] **Step 3: Add the model**

Append to `backend/app/models/cacm.py`:

```python
class CacmSchedule(Base):
    """Scheduled recurring run of a single CACM KRI.

    One row per (org, process, KRI). Saving the same KRI again upserts
    frequency/time/next_run_at. The `kpi_type` is denormalized at create
    time so the scheduler doesn't depend on the catalog at fire time.
    """

    __tablename__ = "cacm_schedules"
    __table_args__ = (
        UniqueConstraint(
            "org_id", "process_key", "kri_name",
            name="uq_cacm_schedule_org_process_kri",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    process_key: Mapped[str] = mapped_column(String(64), nullable=False)
    kri_name: Mapped[str] = mapped_column(String(255), nullable=False)
    kpi_type: Mapped[str] = mapped_column(String(80), nullable=False)
    frequency: Mapped[str] = mapped_column(String(16), nullable=False)
    time_of_day: Mapped[str] = mapped_column(String(5), nullable=False)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_id: Mapped[int | None] = mapped_column(
        ForeignKey("cacm_runs.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="1"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    last_run = relationship("CacmRun", foreign_keys=[last_run_id])
```

Add `Boolean` to the existing import line at the top of the file:

```python
from sqlalchemy import (
    Boolean, String, Integer, Float, Text, DateTime, ForeignKey, JSON,
    UniqueConstraint, func,
)
```

- [ ] **Step 4: Re-export in models package**

Edit `backend/app/models/__init__.py`:

```python
from app.models.cacm import CacmRun, CacmRunEvent, CacmException, CacmSchedule
```

And in `__all__`:

```python
__all__ = [
    "User",
    "Organization",
    "Department",
    "Membership",
    "DepartmentMembership",
    "OrgRole",
    "Agent",
    "AgentDepartment",
    "AgentRun",
    "KnowledgeDoc",
    "AuditLog",
    "Integration",
    "Invite",
    "UserAgent",
    "CacmRun",
    "CacmRunEvent",
    "CacmException",
    "CacmSchedule",
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_models.py -v`
Expected: 2 passed.

- [ ] **Step 6: Run the full CACM model+route test suite to confirm nothing else broke**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_models.py tests/test_cacm_routes.py tests/test_cacm_processes.py -q`
Expected: all green.

- [ ] **Step 7: Checkpoint**

Stop here for review.

---

## Task 3: Alembic migration

**Files:**
- Create: `backend/alembic/versions/<new_rev>_add_cacm_schedules.py`

- [ ] **Step 1: Generate the revision**

Run: `cd backend && ./venv/bin/alembic revision -m "add cacm schedules"`
Expected output: a new file under `alembic/versions/<new_rev>_add_cacm_schedules.py` with `down_revision = 'fcfc43cd930e'` (the current head). If the down_revision is wrong, edit it manually.

- [ ] **Step 2: Fill in the migration body**

Replace the body of the new file with:

```python
"""add cacm schedules

Adds the cacm_schedules table that backs the per-KRI scheduling feature
(see docs/superpowers/specs/2026-05-08-cacm-kri-scheduling-design.md).
One row per (org, process_key, kri_name); upsert semantics on save.

Revision ID: <generated>
Revises: fcfc43cd930e
Create Date: <generated>
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "<generated>"
down_revision: Union[str, Sequence[str], None] = "fcfc43cd930e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cacm_schedules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "org_id", sa.Integer(),
            sa.ForeignKey("organizations.id", ondelete="CASCADE"),
            nullable=False, index=True,
        ),
        sa.Column(
            "user_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("process_key", sa.String(length=64), nullable=False),
        sa.Column("kri_name", sa.String(length=255), nullable=False),
        sa.Column("kpi_type", sa.String(length=80), nullable=False),
        sa.Column("frequency", sa.String(length=16), nullable=False),
        sa.Column("time_of_day", sa.String(length=5), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_run_id", sa.Integer(),
            sa.ForeignKey("cacm_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            nullable=False, server_default=sa.text("1"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "org_id", "process_key", "kri_name",
            name="uq_cacm_schedule_org_process_kri",
        ),
    )
    op.create_index(
        "ix_cacm_schedules_active_due",
        "cacm_schedules",
        ["is_active", "next_run_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cacm_schedules_active_due", table_name="cacm_schedules")
    op.drop_table("cacm_schedules")
```

(Replace the two `<generated>` placeholders inside the docstring + `revision` with the value Alembic produced.)

- [ ] **Step 3: Apply the migration**

Run: `cd backend && ./venv/bin/alembic upgrade head`
Expected: "Running upgrade fcfc43cd930e -> <new_rev>, add cacm schedules" with no error.

- [ ] **Step 4: Confirm rollback works**

Run: `cd backend && ./venv/bin/alembic downgrade -1 && ./venv/bin/alembic upgrade head`
Expected: clean down + up cycle.

- [ ] **Step 5: Checkpoint**

Stop here for review.

---

## Task 4: Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/cacm.py`

- [ ] **Step 1: Append the new schemas**

Add these classes to the end of `backend/app/schemas/cacm.py`:

```python
# ── Schedules ────────────────────────────────────────────────────────────────


from typing import Literal


_FREQ = Literal[
    "daily", "weekly", "monthly", "quarterly", "half_yearly", "annually",
]


class ScheduleCreate(BaseModel):
    process_key: str = Field(min_length=1, max_length=64)
    kri_name: str = Field(min_length=1, max_length=255)
    frequency: _FREQ
    time_of_day: str = Field(pattern=r"^[0-2]\d:[0-5]\d$")


class ScheduleUpdate(BaseModel):
    frequency: _FREQ
    time_of_day: str = Field(pattern=r"^[0-2]\d:[0-5]\d$")


class ScheduleSummary(BaseModel):
    id: int
    process_key: str
    kri_name: str
    kpi_type: str
    frequency: str
    time_of_day: str
    next_run_at: datetime
    last_run_at: datetime | None
    last_run_id: int | None
    is_active: bool

    model_config = {"from_attributes": True}


class SchedulesResponse(BaseModel):
    schedules: list[ScheduleSummary]
```

- [ ] **Step 2: Smoke-import to make sure the file still parses**

Run: `cd backend && ./venv/bin/python -c "from app.schemas.cacm import ScheduleCreate, ScheduleUpdate, ScheduleSummary, SchedulesResponse; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Validate the regex catches bad time strings**

Run: `cd backend && ./venv/bin/python -c "
from pydantic import ValidationError
from app.schemas.cacm import ScheduleCreate
try:
    ScheduleCreate(process_key='p', kri_name='k', frequency='daily', time_of_day='9am')
    print('FAIL — should have rejected')
except ValidationError:
    print('rejected ok')
ScheduleCreate(process_key='p', kri_name='k', frequency='daily', time_of_day='09:00')
print('accepted ok')
"`
Expected: `rejected ok` then `accepted ok`.

- [ ] **Step 4: Checkpoint**

Stop here for review.

---

## Task 5: Schedules CRUD routes (TDD)

**Files:**
- Modify: `backend/app/api/routes/cacm.py`
- Test: `backend/tests/test_cacm_schedule_routes.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_cacm_schedule_routes.py
"""HTTP-level tests for /api/cacm/schedules CRUD."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import OrgContext, get_db, require_org
from app.core.database import Base
from app.main import app
from app.models import Organization, User


@pytest.fixture
def client():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    LocalSession = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    with LocalSession() as s:
        org_a = Organization(name="A", slug="a", is_active=True)
        org_b = Organization(name="B", slug="b", is_active=True)
        user = User(email="a@b.c", name="A", password_hash="x",
                    is_super_admin=False, is_active=True)
        s.add_all([org_a, org_b, user])
        s.commit()
        s.refresh(org_a)
        s.refresh(org_b)
        s.refresh(user)
        ids = (org_a.id, org_b.id, user.id)

    def _override_db():
        s = LocalSession()
        try:
            yield s
        finally:
            s.close()

    org_a_id, _org_b_id, user_id = ids
    active = {"org_id": org_a_id}

    def _override_require_org():
        with LocalSession() as ses:
            u = ses.get(User, user_id)
            return OrgContext(user=u, membership=None, org_id=active["org_id"])

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[require_org] = _override_require_org
    try:
        yield TestClient(app), ids, active
    finally:
        app.dependency_overrides.clear()


def test_post_schedule_creates_and_resolves_kpi_type(client):
    c, _ids, _active = client
    r = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    })
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["kpi_type"] == "po_after_invoice"
    assert body["frequency"] == "daily"
    assert body["time_of_day"] == "09:00"
    assert body["last_run_id"] is None
    assert body["next_run_at"]


def test_post_schedule_rejects_unknown_kri(client):
    c, _, _ = client
    r = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "made up kri name",
        "frequency": "daily",
        "time_of_day": "09:00",
    })
    assert r.status_code == 400


def test_post_schedule_upserts_on_same_kri(client):
    c, _, _ = client
    body = {
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }
    r1 = c.post("/api/cacm/schedules", json=body)
    assert r1.status_code == 201
    body["frequency"] = "weekly"
    r2 = c.post("/api/cacm/schedules", json=body)
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.json()["frequency"] == "weekly"


def test_get_schedules_filters_by_process(client):
    c, _, _ = client
    c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    })
    c.post("/api/cacm/schedules", json={
        "process_key": "inventory_management",
        "kri_name": "Repeated adjustments for same materials",
        "frequency": "weekly",
        "time_of_day": "10:00",
    })
    all_ = c.get("/api/cacm/schedules").json()["schedules"]
    assert len(all_) == 2
    only_p2p = c.get("/api/cacm/schedules", params={
        "process_key": "procurement_to_payment",
    }).json()["schedules"]
    assert len(only_p2p) == 1
    assert only_p2p[0]["process_key"] == "procurement_to_payment"


def test_put_schedule_updates_and_recomputes_next(client):
    c, _, _ = client
    created = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }).json()
    r = c.put(f"/api/cacm/schedules/{created['id']}", json={
        "frequency": "weekly",
        "time_of_day": "10:30",
    })
    assert r.status_code == 200
    out = r.json()
    assert out["frequency"] == "weekly"
    assert out["time_of_day"] == "10:30"
    assert out["next_run_at"] != created["next_run_at"]


def test_delete_schedule(client):
    c, _, _ = client
    created = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }).json()
    r = c.delete(f"/api/cacm/schedules/{created['id']}")
    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert c.get("/api/cacm/schedules").json()["schedules"] == []


def test_get_404_for_other_org_schedule(client):
    c, ids, active = client
    org_a_id, org_b_id, _user_id = ids
    created = c.post("/api/cacm/schedules", json={
        "process_key": "procurement_to_payment",
        "kri_name": "PO issued after invoice date (retroactive approvals)",
        "frequency": "daily",
        "time_of_day": "09:00",
    }).json()
    # Switch the override to the other org and try to mutate.
    active["org_id"] = org_b_id
    try:
        r = c.put(f"/api/cacm/schedules/{created['id']}", json={
            "frequency": "weekly", "time_of_day": "09:00",
        })
        assert r.status_code == 404
        r = c.delete(f"/api/cacm/schedules/{created['id']}")
        assert r.status_code == 404
    finally:
        active["org_id"] = org_a_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_routes.py -v`
Expected: 404s on all routes (handlers don't exist yet).

- [ ] **Step 3: Implement the routes**

In `backend/app/api/routes/cacm.py`, add to the imports near the top:

```python
from datetime import datetime, timedelta, timezone

from app.agents.cacm.schedule_math import compute_next_run_at
from app.models.cacm import CacmException, CacmRun, CacmRunEvent, CacmSchedule
from app.schemas.cacm import (
    # ... existing ...
    ScheduleCreate,
    ScheduleSummary,
    ScheduleUpdate,
    SchedulesResponse,
)
```

(Keep the existing import list intact — just add the four new names.)

Add this block right after the `get_process_detail` route (~ line 132):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_routes.py -v`
Expected: 7 passed.

- [ ] **Step 5: Run the full CACM test suite**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_*.py -q`
Expected: all green.

- [ ] **Step 6: Checkpoint**

Stop here for review.

---

## Task 6: Background scheduler (TDD)

**Files:**
- Create: `backend/app/agents/cacm/scheduler.py`
- Test: `backend/tests/test_cacm_schedule_scheduler.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_cacm_schedule_scheduler.py
"""Scheduler tick logic — does it pick up due schedules and advance them?"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents.cacm.scheduler import scheduler_tick
from app.core.database import Base
from app.models import CacmRun, CacmSchedule, Organization, User


@pytest.fixture
def session_factory(monkeypatch):
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    LocalSession = sessionmaker(bind=eng, autoflush=False, autocommit=False, future=True)
    return LocalSession


@pytest.fixture
def seeded(session_factory, monkeypatch):
    s = session_factory()
    org = Organization(name="X", slug="x", is_active=True)
    user = User(email="a@b.c", name="A", password_hash="x",
                is_super_admin=False, is_active=True)
    s.add_all([org, user])
    s.commit()
    s.refresh(org)
    s.refresh(user)
    org_id = org.id
    user_id = user.id
    s.close()

    # Stub the pipeline kickoff so the test stays synchronous.
    fired = []

    async def _fake_run_in_background(run_id):
        fired.append(run_id)

    monkeypatch.setattr(
        "app.agents.cacm.scheduler._run_in_background", _fake_run_in_background,
    )
    return session_factory, org_id, user_id, fired


def _due_row(org_id, user_id, **overrides):
    base = dict(
        org_id=org_id,
        user_id=user_id,
        process_key="procurement_to_payment",
        kri_name="PO issued after invoice date (retroactive approvals)",
        kpi_type="po_after_invoice",
        frequency="daily",
        time_of_day="09:00",
        next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        is_active=True,
    )
    base.update(overrides)
    return CacmSchedule(**base)


def test_tick_fires_due_schedule_and_advances_next_run(seeded):
    factory, org_id, user_id, fired = seeded
    s = factory()
    s.add(_due_row(org_id, user_id))
    s.commit()
    s.close()

    scheduler_tick(factory)

    s = factory()
    sched = s.query(CacmSchedule).one()
    runs = s.query(CacmRun).all()
    assert len(runs) == 1
    assert runs[0].kpi_type == "po_after_invoice"
    assert runs[0].status == "running"
    assert sched.last_run_id == runs[0].id
    assert sched.last_run_at is not None
    assert sched.next_run_at > datetime.now(timezone.utc)
    assert fired == [runs[0].id]
    s.close()


def test_tick_skips_inactive_schedules(seeded):
    factory, org_id, user_id, fired = seeded
    s = factory()
    s.add(_due_row(org_id, user_id, is_active=False))
    s.commit()
    s.close()

    scheduler_tick(factory)

    s = factory()
    assert s.query(CacmRun).count() == 0
    assert fired == []
    s.close()


def test_tick_skips_future_schedules(seeded):
    factory, org_id, user_id, fired = seeded
    s = factory()
    s.add(_due_row(
        org_id, user_id,
        next_run_at=datetime.now(timezone.utc) + timedelta(hours=1),
    ))
    s.commit()
    s.close()

    scheduler_tick(factory)

    s = factory()
    assert s.query(CacmRun).count() == 0
    assert fired == []
    s.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_scheduler.py -v`
Expected: ImportError on `from app.agents.cacm.scheduler import scheduler_tick`.

- [ ] **Step 3: Write the scheduler**

Create `backend/app/agents/cacm/scheduler.py`:

```python
"""Background scheduler for CACM KRI schedules.

Single asyncio loop started on FastAPI lifespan. Every 60 s it:
  1. Finds active schedules where next_run_at <= now.
  2. Creates a CacmRun for each and kicks off `_run_in_background`.
  3. Advances `next_run_at` per the schedule's frequency.

`scheduler_tick` is the synchronous core, exposed for direct testing.
The async loop wraps it and handles cancellation + error logging.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session, sessionmaker

from app.agents.cacm.schedule_math import compute_next_run_at
from app.models.cacm import CacmRun, CacmSchedule


log = logging.getLogger(__name__)

# Imported indirectly so tests can monkeypatch the symbol.
from app.api.routes.cacm import _run_in_background  # noqa: E402


_TICK_INTERVAL_SECONDS = 60


def scheduler_tick(session_factory: Callable[[], Session]) -> None:
    """Run one pass over due schedules. Synchronous; safe to call from tests."""
    db = session_factory()
    try:
        now = datetime.now(timezone.utc)
        due = (
            db.query(CacmSchedule)
            .filter(
                CacmSchedule.is_active == True,  # noqa: E712
                CacmSchedule.next_run_at <= now,
            )
            .all()
        )
        for sched in due:
            run = CacmRun(
                org_id=sched.org_id,
                user_id=sched.user_id,
                kpi_type=sched.kpi_type,
                process=_process_label(sched.kpi_type),
                status="running",
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            try:
                asyncio.get_event_loop().create_task(_run_in_background(run.id))
            except RuntimeError:
                # No running loop in tests — fall through; tests stub
                # `_run_in_background` to a sync no-op so this branch
                # only matters for the test path.
                asyncio.run(_run_in_background(run.id))

            sched.last_run_id = run.id
            sched.last_run_at = now
            sched.next_run_at = compute_next_run_at(
                sched.frequency, sched.time_of_day, now=now,
            )
            db.commit()
    finally:
        db.close()


def _process_label(kpi_type: str) -> str:
    """Mirror what POST /runs does: read the KPI catalog to get the
    process label that gets stored on CacmRun."""
    from app.agents.cacm.kpi_catalog import kpi_by_type
    kpi = kpi_by_type(kpi_type)
    return kpi.process if kpi else "unknown"


async def scheduler_loop(session_factory: Callable[[], Session]) -> None:
    """Long-running async loop. Cancellation-safe."""
    while True:
        try:
            scheduler_tick(session_factory)
        except Exception:
            log.exception("CACM scheduler tick failed")
        try:
            await asyncio.sleep(_TICK_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && ./venv/bin/python -m pytest tests/test_cacm_schedule_scheduler.py -v`
Expected: 3 passed.

- [ ] **Step 5: Checkpoint**

Stop here for review.

---

## Task 7: Wire the scheduler into FastAPI lifespan

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: Modify the lifespan to start/stop the loop**

In `backend/app/main.py`, replace the `lifespan` function:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Schema is managed by Alembic — run `alembic upgrade head` before first start.
    insp = inspect(engine)
    if not insp.has_table("alembic_version"):
        raise RuntimeError(
            "Database is not initialized. Run `alembic upgrade head` from backend/ "
            "before starting the app."
        )

    db = SessionLocal()
    try:
        _ensure_bootstrap_super_admin(db)
    finally:
        db.close()

    # CACM schedule loop — single in-process scheduler. See
    # docs/superpowers/specs/2026-05-08-cacm-kri-scheduling-design.md.
    from app.agents.cacm.scheduler import scheduler_loop
    scheduler_task = asyncio.create_task(scheduler_loop(SessionLocal))

    try:
        yield
    finally:
        scheduler_task.cancel()
        try:
            await scheduler_task
        except asyncio.CancelledError:
            pass
```

Add `import asyncio` at the top of the file (alongside the existing imports).

- [ ] **Step 2: Smoke-test the app boots**

Run: `cd backend && ./venv/bin/python -c "from app.main import app; print('imports ok')"`
Expected: `imports ok` with no errors.

- [ ] **Step 3: Run all backend tests**

Run: `cd backend && ./venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 4: Checkpoint**

Stop here for review.

---

## Task 8: Frontend api.js — schedule wrappers

**Files:**
- Modify: `frontend/src/cacm/api.js`

- [ ] **Step 1: Append the four wrappers**

Add to `frontend/src/cacm/api.js` just after `useEvents`:

```js
/* ── Schedules ────────────────────────────────────────────────────────── */

/** Create or upsert a schedule. The backend uses (org, process_key, kri_name)
 *  uniqueness — re-saving the same KRI returns the same id with new freq/time.
 *  Body: { process_key, kri_name, frequency, time_of_day }
 */
export async function createSchedule(body) {
  const { data } = await API.post("/schedules", body);
  return data;
}

/** List schedules for the current org, optionally filtered to one process. */
export async function listSchedules({ processKey } = {}) {
  const params = {};
  if (processKey) params.process_key = processKey;
  const { data } = await API.get("/schedules", { params });
  return data;
}

/** Edit a schedule's frequency and time. */
export async function updateSchedule(id, body) {
  const { data } = await API.put(`/schedules/${id}`, body);
  return data;
}

/** Delete a schedule. */
export async function deleteSchedule(id) {
  const { data } = await API.delete(`/schedules/${id}`);
  return data;
}
```

- [ ] **Step 2: Verify the file still parses**

Run: `cd frontend && npx --yes esbuild src/cacm/api.js --bundle --outfile=/dev/null --platform=browser --format=esm --loader:.js=jsx 2>&1 | head -20`
Expected: no errors. (If esbuild isn't available, run `npm run build` instead and look only at this file's diagnostics.)

- [ ] **Step 3: Checkpoint**

Stop here for review.

---

## Task 9: ScheduleModal component

**Files:**
- Create: `frontend/src/cacm/components/ScheduleModal.jsx`
- Modify: `frontend/src/cacm/styles.css`

- [ ] **Step 1: Create the component**

Create `frontend/src/cacm/components/ScheduleModal.jsx`:

```jsx
import React, { useState } from "react";
import {
  createSchedule,
  deleteSchedule,
  updateSchedule,
} from "../api.js";

/** ScheduleModal — create/edit/delete a recurring schedule for a single KRI.
 *
 *  Props:
 *    mode:        "create" | "edit"
 *    processKey:  string
 *    kriName:     string
 *    schedule:    existing ScheduleSummary (only in edit mode)
 *    onClose():   user dismissed without saving
 *    onSaved(s):  successful create or update — receives ScheduleSummary
 *    onDeleted(): successful delete
 */
const FREQUENCY_OPTIONS = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "half_yearly", label: "Half-yearly" },
  { value: "annually", label: "Annually" },
];

function _formatLocal(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function ScheduleModal({
  mode,
  processKey,
  kriName,
  schedule,
  onClose,
  onSaved,
  onDeleted,
}) {
  const [frequency, setFrequency] = useState(
    schedule?.frequency || "daily"
  );
  const [timeOfDay, setTimeOfDay] = useState(
    schedule?.time_of_day || "09:00"
  );
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const validTime = /^[0-2]\d:[0-5]\d$/.test(timeOfDay);
  const canSave = !!frequency && validTime && !busy;

  async function handleSave() {
    setBusy(true);
    setErr("");
    try {
      if (mode === "edit" && schedule) {
        const out = await updateSchedule(schedule.id, {
          frequency,
          time_of_day: timeOfDay,
        });
        onSaved(out);
      } else {
        const out = await createSchedule({
          process_key: processKey,
          kri_name: kriName,
          frequency,
          time_of_day: timeOfDay,
        });
        onSaved(out);
      }
    } catch (e) {
      setErr(
        e.response?.data?.detail || e.message || "Failed to save schedule."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleDelete() {
    if (!schedule) return;
    if (!window.confirm("Delete this schedule?")) return;
    setBusy(true);
    setErr("");
    try {
      await deleteSchedule(schedule.id);
      onDeleted();
    } catch (e) {
      setErr(
        e.response?.data?.detail || e.message || "Failed to delete schedule."
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="cacm-schedule-modal-overlay" onClick={onClose}>
      <div
        className="cacm-schedule-modal-card"
        role="dialog"
        aria-label="Schedule KRI"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="cacm-schedule-modal-head">
          <div className="cacm-schedule-modal-title">
            {mode === "edit" ? "Edit schedule" : "Schedule KRI"}
          </div>
          <div className="cacm-schedule-modal-sub">{kriName}</div>
        </div>

        <div className="cacm-schedule-modal-body">
          <label className="cacm-schedule-modal-field">
            <span>Frequency</span>
            <select
              value={frequency}
              onChange={(e) => setFrequency(e.target.value)}
              disabled={busy}
            >
              {FREQUENCY_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>

          <label className="cacm-schedule-modal-field">
            <span>Time of run</span>
            <input
              type="time"
              value={timeOfDay}
              onChange={(e) => setTimeOfDay(e.target.value)}
              disabled={busy}
            />
          </label>

          {mode === "edit" && schedule && (
            <div className="cacm-schedule-modal-meta">
              <div>
                <span>Next run</span>
                <strong>{_formatLocal(schedule.next_run_at)}</strong>
              </div>
              <div>
                <span>Last run</span>
                <strong>{_formatLocal(schedule.last_run_at)}</strong>
              </div>
            </div>
          )}

          {err && <div className="inv-warning">{err}</div>}
        </div>

        <div className="cacm-schedule-modal-foot">
          {mode === "edit" && (
            <button
              type="button"
              className="btn"
              onClick={handleDelete}
              disabled={busy}
            >
              Delete
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button
            type="button"
            className="btn"
            onClick={onClose}
            disabled={busy}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSave}
            disabled={!canSave}
          >
            {busy ? "Saving…" : mode === "edit" ? "Save changes" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Add the styles**

Append to `frontend/src/cacm/styles.css`:

```css
/* ── Schedule modal ─────────────────────────────────────────────────── */

.cacm-schedule-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 16px;
}

.cacm-schedule-modal-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  width: min(440px, 100%);
  display: flex;
  flex-direction: column;
  max-height: calc(100vh - 32px);
  overflow: hidden;
  box-shadow: 0 10px 30px rgba(0, 0, 0, 0.25);
}

.cacm-schedule-modal-head {
  padding: 18px 20px 12px;
  border-bottom: 1px solid var(--border);
}
.cacm-schedule-modal-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--ink);
}
.cacm-schedule-modal-sub {
  font-size: 13px;
  color: var(--ink-muted);
  margin-top: 4px;
}

.cacm-schedule-modal-body {
  padding: 16px 20px;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-y: auto;
}

.cacm-schedule-modal-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--ink-dim);
}
.cacm-schedule-modal-field select,
.cacm-schedule-modal-field input[type="time"] {
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--ink);
  font-size: 14px;
}

.cacm-schedule-modal-meta {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  padding: 12px;
  background: var(--bg-card-hover, rgba(0, 0, 0, 0.03));
  border-radius: 8px;
  font-size: 12px;
}
.cacm-schedule-modal-meta div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.cacm-schedule-modal-meta span {
  color: var(--ink-muted);
}
.cacm-schedule-modal-meta strong {
  color: var(--ink);
  font-weight: 600;
}

.cacm-schedule-modal-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--border);
}

/* ── KRI row split into name + actions ──────────────────────────────── */

.cacm-kri-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 14px;
  align-items: center;
  padding: 14px 18px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 10px;
}
.cacm-kri-row:hover {
  border-color: var(--accent);
}

.cacm-kri-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.cacm-kri-eye {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-card);
  color: var(--ink);
  cursor: pointer;
  font-size: 16px;
}
.cacm-kri-eye:hover {
  border-color: var(--accent);
  color: var(--accent);
}
```

- [ ] **Step 3: Build to confirm no errors**

Run: `cd frontend && npm run build 2>&1 | tail -30`
Expected: build succeeds. (If the project uses a different build command, substitute it here — see frontend/package.json scripts.)

- [ ] **Step 4: Checkpoint**

Stop here for review.

---

## Task 10: Wire ScheduleModal into ProcessDetailPage

**Files:**
- Modify: `frontend/src/cacm/pages/ProcessDetailPage.jsx`

- [ ] **Step 1: Replace the file**

Overwrite `frontend/src/cacm/pages/ProcessDetailPage.jsx` with:

```jsx
import React, { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import AppShell from "../../components/AppShell.jsx";
import { getProcess, listSchedules, startRun } from "../api.js";
import ScheduleModal from "../components/ScheduleModal.jsx";
import "../styles.css";

/** ProcessDetailPage — /agents/cacm/processes/:processKey. Each KRI row
 *  has explicit Run + Schedule actions, and an eye-icon view button when
 *  a schedule already exists for that KRI.
 */
export default function ProcessDetailPage() {
  const { processKey } = useParams();
  const navigate = useNavigate();
  const [process, setProcess] = useState(null);
  const [schedulesByKri, setSchedulesByKri] = useState(new Map());
  const [err, setErr] = useState("");
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState("");
  const [modal, setModal] = useState(null); // { mode, kriName, schedule? }

  async function loadSchedules() {
    try {
      const data = await listSchedules({ processKey });
      const map = new Map();
      for (const s of data.schedules || []) {
        map.set(s.kri_name, s);
      }
      setSchedulesByKri(map);
    } catch (e) {
      // Non-fatal: page still works without schedule indicators.
      console.error("listSchedules failed", e);
    }
  }

  useEffect(() => {
    let cancelled = false;
    setProcess(null);
    setErr("");
    getProcess(processKey)
      .then((data) => {
        if (cancelled) return;
        setProcess(data);
      })
      .catch((e) => {
        if (cancelled) return;
        const status = e.response?.status;
        if (status === 404) setErr("Process not found.");
        else
          setErr(
            e.response?.data?.detail || e.message || "Failed to load process."
          );
      });
    loadSchedules();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [processKey]);

  async function handleRun(kri) {
    if (!kri.kpi_type || starting) return;
    setStarting(true);
    setStartError("");
    try {
      const data = await startRun(kri.kpi_type);
      if (!data?.run_id) throw new Error("Backend did not return a run_id.");
      navigate(`/agents/cacm/run/${data.run_id}`);
    } catch (e) {
      setStartError(
        e.response?.data?.detail || e.message || "Failed to start run."
      );
    } finally {
      setStarting(false);
    }
  }

  function openCreate(kri) {
    setModal({ mode: "create", kriName: kri.name });
  }
  function openEdit(kri) {
    const existing = schedulesByKri.get(kri.name);
    if (!existing) return;
    setModal({ mode: "edit", kriName: kri.name, schedule: existing });
  }

  const kris = useMemo(() => process?.kris || [], [process]);

  return (
    <AppShell crumbs={["Agent Hub", "Prism", process?.name || "Process"]}>
      <div className="cacm-hero">
        <div style={{ flex: 1, minWidth: 0 }}>
          <Link to="/agents/cacm" className="cacm-back-link">
            ← All Processes
          </Link>
          <h1 className="page-title" style={{ marginTop: 8, marginBottom: 6 }}>
            {process?.name || "…"}
          </h1>
          {process && (
            <div className="page-subtitle" style={{ marginBottom: 10 }}>
              {process.intro}
            </div>
          )}
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <Link to="/agents/cacm/runs" className="btn">
            Run history
          </Link>
          <Link to="/agents/cacm" className="btn">
            ← All processes
          </Link>
        </div>
      </div>

      {err && <div className="inv-warning">{err}</div>}
      {startError && <div className="inv-warning">{startError}</div>}
      {starting && <div className="cacm-loading">Starting run…</div>}

      {!err && process === null && (
        <div className="cacm-loading">Loading process…</div>
      )}

      {!err && process && kris.length > 0 && (
        <div className="cacm-kri-list">
          {kris.map((kri, idx) => {
            const scheduled = schedulesByKri.get(kri.name);
            return (
              <div
                key={`${kri.kpi_type || "kri"}-${idx}`}
                className="cacm-kri-row"
              >
                <div className="cacm-kri-item-main">
                  <div className="cacm-kri-item-name">{kri.name}</div>
                </div>
                <div className="cacm-kri-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => handleRun(kri)}
                    disabled={!kri.kpi_type || starting}
                  >
                    ▶ Run
                  </button>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => openCreate(kri)}
                    disabled={starting}
                    title="Create / replace recurring schedule"
                  >
                    ⏱ Schedule
                  </button>
                  {scheduled && (
                    <button
                      type="button"
                      className="cacm-kri-eye"
                      aria-label="View schedule"
                      title="View schedule"
                      onClick={() => openEdit(kri)}
                    >
                      👁
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {modal && (
        <ScheduleModal
          mode={modal.mode}
          processKey={processKey}
          kriName={modal.kriName}
          schedule={modal.schedule}
          onClose={() => setModal(null)}
          onSaved={async () => {
            setModal(null);
            await loadSchedules();
          }}
          onDeleted={async () => {
            setModal(null);
            await loadSchedules();
          }}
        />
      )}
    </AppShell>
  );
}
```

- [ ] **Step 2: Build the frontend**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: build succeeds.

- [ ] **Step 3: Manual smoke test**

Start backend (`cd backend && ./venv/bin/uvicorn app.main:app --reload`) and frontend (`cd frontend && npm run dev`). Navigate to a process detail page and confirm:
- Each KRI row shows `▶ Run`, `⏱ Schedule`, and no eye icon initially.
- Clicking `⏱ Schedule` opens the modal; saving closes it and the eye icon appears.
- Clicking 👁 reopens the modal in edit mode with the saved values + Delete button.
- Deleting the schedule removes the eye icon.
- Clicking `▶ Run` still navigates to the run page (existing behavior).

- [ ] **Step 4: Checkpoint**

Stop here for review.

---

## Task 11: Remove "Schedule whole process" button from RunPage

**Files:**
- Modify: `frontend/src/cacm/pages/RunPage.jsx`

- [ ] **Step 1: Remove the button block in ExtractionStage**

In `frontend/src/cacm/pages/RunPage.jsx`, find this block in `ExtractionStage` (currently at ~lines 257–267):

```jsx
            {!autopilot && onScheduleAll && (
              <button
                type="button"
                className="btn"
                onClick={onScheduleAll}
                disabled={running}
                title="Auto-run every stage and land on the Exception Report when done."
              >
                ▶︎ Schedule whole process
              </button>
            )}
```

Delete those lines.

- [ ] **Step 2: Drop `onScheduleAll` from the prop list**

In the same file, remove `onScheduleAll,` from `ExtractionStage`'s destructured props (currently at ~line 107):

```jsx
function ExtractionStage({
  runId,
  kpiMeta,
  onComplete,
  completed,
  autopilot,
}) {
```

- [ ] **Step 3: Stop passing `onScheduleAll` from the parent**

Find the `<ExtractionStage … onScheduleAll={() => setAutopilot(true)} />` call (currently at ~line 1162) and remove the `onScheduleAll` prop. The `setAutopilot(true)` callback is no longer needed from this site — autopilot still has any other entry points the rest of the wizard provides.

- [ ] **Step 4: Build the frontend**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: build succeeds with no warnings about unused vars.

- [ ] **Step 5: Smoke test**

Reload the run wizard in the browser and confirm Stage 1 no longer shows the "Schedule whole process" button. Other Stage 1 functionality (Run Data Extraction, source dropdown) is unchanged.

- [ ] **Step 6: Checkpoint**

Stop here for review.

---

## Task 12: Final integration pass

- [ ] **Step 1: Run the full backend test suite**

Run: `cd backend && ./venv/bin/python -m pytest -q`
Expected: all green.

- [ ] **Step 2: Build the frontend cleanly**

Run: `cd frontend && npm run build 2>&1 | tail -10`
Expected: build succeeds.

- [ ] **Step 3: End-to-end manual test**

With backend + frontend running:

1. Navigate to a process detail page. KRI rows show three buttons (Run / Schedule, plus Eye if scheduled).
2. Schedule a KRI for "daily at <2 minutes from now>". (Use a quick frequency to validate the scheduler.)
3. Wait ≥ 2 minutes; verify a new run shows up under Run History (the scheduler tick fires every 60 s).
4. Open the eye icon — modal shows the saved frequency, time, and `Last run` populated with the most recent run.
5. Edit the schedule to weekly + a different time → reopen the eye icon → values persist.
6. Delete the schedule → eye icon disappears, GET /api/cacm/schedules returns nothing for that KRI.
7. Visit a run wizard's Stage 1 — the "Schedule whole process" button is gone.

- [ ] **Step 4: Checkpoint**

Final review with user. The user will handle git from here.

---

## Self-Review

- **Spec coverage** — every section of the spec is mapped to at least one task:
  - 3.1 model → Task 2 + Task 3
  - 3.2 frequency mapping → Task 1 (`compute_next_run_at`)
  - 4.1–4.3 backend → Tasks 2–5
  - 4.4 scheduler → Tasks 6–7
  - 4.5 tests → covered inside each task (TDD-first)
  - 5.1 api.js → Task 8
  - 5.2 ProcessDetailPage → Task 10
  - 5.3 ScheduleModal → Task 9
  - 5.4 RunPage cleanup → Task 11
  - 5.5 styles → Task 9 (modal + KRI row styles in one go to stay focused)
- **No placeholders** — every code block is complete.
- **Type / name consistency** — `compute_next_run_at(frequency, time_of_day, *, now)` signature is identical across `schedule_math.py`, the route, and the scheduler. `ScheduleSummary` field names match between schemas, model, and frontend usage. `processKey` (camelCase) is the React prop convention; `process_key` (snake_case) is the API convention — both intentional.
- **Frequent commit cadence** — the user manages git themselves; each task has a Checkpoint instead.
