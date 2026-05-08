# CACM KRI-Level Run & Schedule — Design

**Date:** 2026-05-08
**Status:** Approved (verbal)
**Scope:** Add per-KRI Run and Schedule controls to the CACM Process Detail page,
with backend persistence and real cron-like execution. Remove the legacy
"Schedule whole process" button from the run wizard.

---

## 1. Motivation

Today, every KRI row on `/agents/cacm/processes/:processKey` is a single
button that immediately starts a run. The only "schedule" affordance is a
mis-labelled `▶︎ Schedule whole process` button on Stage 1 of the run wizard,
which actually toggles autopilot through the wizard stages — not a real
schedule.

Auditors want to:

1. Run a KRI on demand (existing behavior, but now an explicit Run action).
2. Schedule a KRI to run automatically on a recurring cadence
   (daily / weekly / monthly / quarterly / half-yearly / annually) at a chosen
   time of day.
3. See at a glance which KRIs are scheduled, and view / edit / delete the
   schedule.

## 2. Out of scope

- Multi-tenant timezone handling beyond a single server timezone (UTC stored,
  rendered in server local time).
- Per-user scheduling overrides — schedules are per-org, last writer wins.
- Cluster-safe scheduling (multiple uvicorn workers racing). Single-process
  uvicorn is the deployment target. A future migration can add `SELECT …
  FOR UPDATE SKIP LOCKED` when needed.
- Day-of-week / day-of-month pickers. Schedules anchor relative to creation:
  e.g. "weekly at 09:00" = every 7 days at 09:00 starting from the next
  occurrence ≥ now.

## 3. Data model

### 3.1 New table `cacm_schedules`

| column | type | notes |
|---|---|---|
| `id` | INTEGER PK | |
| `org_id` | INTEGER NOT NULL, FK → `organizations.id` | tenant scope |
| `user_id` | INTEGER NOT NULL, FK → `users.id` | creator (audit only) |
| `process_key` | VARCHAR(64) NOT NULL | matches `ProcessDef.key` |
| `kri_name` | VARCHAR(255) NOT NULL | matches `KriSummary.name` in catalog |
| `kpi_type` | VARCHAR(80) NOT NULL | resolved from catalog at create time |
| `frequency` | VARCHAR(16) NOT NULL | enum: `daily`, `weekly`, `monthly`, `quarterly`, `half_yearly`, `annually` |
| `time_of_day` | VARCHAR(5) NOT NULL | `HH:MM` 24-hour, server local time |
| `next_run_at` | DATETIME NOT NULL | UTC; computed on save and after each fire |
| `last_run_at` | DATETIME NULL | UTC |
| `last_run_id` | INTEGER NULL, FK → `cacm_runs.id` | most recent triggered run |
| `is_active` | BOOLEAN NOT NULL DEFAULT TRUE | reserved for future pause/resume |
| `created_at` | DATETIME NOT NULL | UTC |
| `updated_at` | DATETIME NOT NULL | UTC |

**Unique constraint:** `(org_id, process_key, kri_name)` — one schedule per
KRI per org. Re-saving the same KRI is an upsert that replaces frequency/time.

**Index:** `(is_active, next_run_at)` — used by the scheduler poll query.

Alembic revision adds the table; downgrade drops it.

### 3.2 Frequency → period mapping

| frequency | period |
|---|---|
| `daily` | 1 day |
| `weekly` | 7 days |
| `monthly` | +1 calendar month (clamped to last day of month) |
| `quarterly` | +3 calendar months |
| `half_yearly` | +6 calendar months |
| `annually` | +1 calendar year (Feb 29 → Feb 28 in non-leap years) |

`next_run_at` is computed as: anchor = today @ `time_of_day` (server tz);
roll forward by `period` until anchor ≥ now; store as UTC.

## 4. Backend

### 4.1 SQLAlchemy model

`backend/app/models/cacm.py` — add `CacmSchedule(Base)` with the columns
above. Relationships: `last_run` (Many-to-One → `CacmRun`).

### 4.2 Pydantic schemas

`backend/app/schemas/cacm.py` adds:

```python
class ScheduleCreate(BaseModel):
    process_key: str
    kri_name: str
    frequency: Literal["daily","weekly","monthly","quarterly","half_yearly","annually"]
    time_of_day: str  # validated HH:MM

class ScheduleUpdate(BaseModel):
    frequency: Literal[...]
    time_of_day: str

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

### 4.3 Routes (added to `app/api/routes/cacm.py`)

- `POST   /api/cacm/schedules` → `ScheduleSummary`
  Body: `ScheduleCreate`. Looks up `kpi_type` via `process_catalog`; rejects
  if the (`process_key`, `kri_name`) pair is unknown. Upserts on the unique
  constraint — re-saving the same KRI replaces frequency/time and recomputes
  `next_run_at`.

- `GET    /api/cacm/schedules` → `SchedulesResponse`
  Query: `process_key?: str`. Returns the org's schedules, filtered to one
  process when provided. Used by ProcessDetailPage to mark which KRIs have
  the eye icon.

- `PUT    /api/cacm/schedules/{id}` → `ScheduleSummary`
  Body: `ScheduleUpdate`. 404 if not in caller's org. Recomputes
  `next_run_at`.

- `DELETE /api/cacm/schedules/{id}` → `{"deleted": true}`. 404 if not in
  caller's org.

All routes are gated by `require_org` and scoped by `ctx.org_id`, matching
the existing CACM route pattern.

### 4.4 Background scheduler

Single asyncio task started on FastAPI lifespan startup, in
`app/main.py`:

```python
async def _scheduler_loop():
    while True:
        try:
            _tick()
        except Exception:
            log.exception("scheduler tick failed")
        await asyncio.sleep(60)
```

`_tick()` opens a `SessionLocal()`, queries:

```python
schedules = (
    db.query(CacmSchedule)
      .filter(CacmSchedule.is_active == True,
              CacmSchedule.next_run_at <= datetime.now(timezone.utc))
      .all()
)
```

For each schedule:

1. **Idempotency check** — skip if a `CacmRun` for `(org_id, kpi_type)`
   already has `status == "running"` and was created in the last 5 minutes.
2. Create a `CacmRun(org_id=…, user_id=schedule.user_id, kpi_type=…,
   process=…, status="running")`, commit.
3. `asyncio.create_task(run_pipeline_in_background(run.id))` — same helper
   the `POST /runs` route uses.
4. Update `schedule.last_run_at = now`, `schedule.last_run_id = run.id`,
   `schedule.next_run_at = compute_next(schedule)`, commit.

Loop is started inside `lifespan` and cancelled on shutdown.

### 4.5 Tests

- `test_cacm_schedule_models.py` — model round-trip + unique constraint.
- `test_cacm_schedule_routes.py` — POST upserts, GET filters by org, PUT
  recomputes `next_run_at`, DELETE 404s for other orgs.
- `test_cacm_schedule_scheduler.py` — backdate `next_run_at`, run one tick,
  assert a `CacmRun` was created and `next_run_at` advanced. Skip the actual
  pipeline by monkeypatching `run_pipeline_in_background`.
- `test_cacm_schedule_next_run.py` — pure-function test of the
  `compute_next_run_at(frequency, time_of_day, now)` helper across all six
  frequencies, including month-end clamping and leap-year annually.

## 5. Frontend

### 5.1 `frontend/src/cacm/api.js`

Add:

```js
export const createSchedule = (body) =>
  api.post("/cacm/schedules", body).then(r => r.data);
export const listSchedules = (params) =>
  api.get("/cacm/schedules", { params }).then(r => r.data);
export const updateSchedule = (id, body) =>
  api.put(`/cacm/schedules/${id}`, body).then(r => r.data);
export const deleteSchedule = (id) =>
  api.delete(`/cacm/schedules/${id}`).then(r => r.data);
```

### 5.2 `ProcessDetailPage.jsx`

Each KRI row becomes:

```
┌────────────────────────────────────────────────────────────────────┐
│  KRI name                          [▶ Run] [⏱ Schedule] [👁]       │
└────────────────────────────────────────────────────────────────────┘
```

- The eye icon renders only when `schedulesByKri.has(kri.name)`.
- Run is the existing flow.
- Schedule opens `<ScheduleModal mode="create" kri={...} />`.
- Eye opens `<ScheduleModal mode="edit" kri={...} schedule={...} />`.

On mount, fire `getProcess(processKey)` and `listSchedules({process_key})`
in parallel; build a `Map<kri_name, Schedule>`.

After a successful save / delete from the modal, refresh the schedule map.

The existing button-row className `cacm-kri-item` is split into:
`cacm-kri-row` (container) with three buttons inside, replacing the
single-button anchor pattern. Keyboard focus goes to each button
separately.

### 5.3 `ScheduleModal.jsx` (new)

Props: `{ mode: "create" | "edit", processKey, kriName, schedule?, onClose, onSaved, onDeleted }`.

Body:
- Frequency `<select>` — Daily / Weekly / Monthly / Quarterly / Half-yearly / Annually.
- Time `<input type="time">` (HH:MM).
- In `edit` mode: shows `Next run` (formatted) and `Last run` (or "—").
- Footer:
  - `create`: `[Cancel] [Save]`
  - `edit`:   `[Delete] [Cancel] [Save changes]`

Validation: time string must match `^[0-2]\d:[0-5]\d$`. Save is disabled
until both fields are filled.

### 5.4 `RunPage.jsx` cleanup

Remove the `▶︎ Schedule whole process` button on Stage 1 (lines ≈257–267)
and the `onScheduleAll` prop plumbing for `ExtractionStage`. Autopilot
itself stays — only the misleading button is removed.

### 5.5 Styles

Append to `frontend/src/cacm/styles.css`:
- `.cacm-kri-row` — flex row, gap.
- `.cacm-kri-actions` — right-aligned button group.
- `.cacm-kri-eye` — square icon button styled to match `btn`.
- `.cacm-schedule-modal` — overlay + card; reuse existing modal patterns
  if any exist in the project, else introduce a lightweight one scoped to
  CACM.

## 6. Migration & rollout

1. Alembic revision `add_cacm_schedules` — new table only; non-breaking.
2. Backend: model + schemas + routes + scheduler loop + tests.
3. Frontend: api wrappers + ScheduleModal + ProcessDetailPage updates +
   RunPage button removal.
4. No feature flag — feature is additive and unblocking.

## 7. Open risks

- **Server timezone.** Schedules use server-local time-of-day. If the
  deployment moves between timezones, `next_run_at` will appear to shift.
  Acceptable for the demo footprint; documented here.
- **Single-process assumption.** Two uvicorn workers would each fire the
  scheduler tick. Mitigate later with row-level locking; for now,
  deployment is single-process.
- **Catalog drift.** If a KRI is renamed in `process_catalog.py`, existing
  schedules pointing at the old name become orphaned. The catalog is
  static today and changes ship via code review, so we accept the risk
  and surface orphans in the GET response (they still return; the UI just
  won't find a matching row to render the eye icon next to).
