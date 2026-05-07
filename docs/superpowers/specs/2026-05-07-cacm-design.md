# CACM — Continuous Audit & Continuous Monitoring — Design

**Status:** Draft for review · **Author:** brainstorming session, 2026-05-07
**Owner:** souravkumar@uniqus.com

## 1. Purpose

Build a **CACM (Continuous Audit & Continuous Monitoring)** agent that lets leadership and business users walk a KPI/KRI through its end-to-end lifecycle — **Library → Extract → Transform → Load → Rule Engine → Exceptions → Dashboard** — and come away understanding how a CACM solution turns raw ERP data into actionable audit insight.

CACM ships as a fully-functional agent inside the existing hub. The flow it shows is real (the rules genuinely execute and produce the exceptions you see); only the source data is canned — every KPI runs against **prebaked SAP-style sample tables** that ship with the agent rather than a live SAP connection.

## 2. Scope (v1)

### In scope

- A new agent `cacm` registered in the existing CATALOG.
- Library page showing **all 8 business processes** and their KPIs (see §3 for the full catalog of 40 KPIs).
- **All 40 KPIs implemented end-to-end.** Each one extracts → transforms → loads → executes → produces exceptions → drives a dashboard.
- A **rule-pattern library** (seven reusable rule shapes) so each KPI is a small declarative config rather than a hand-rolled function. Adding a 41st KPI ≈ a dozen lines.
- Per-process sample data sets engineered so each KPI produces a believable number of exceptions (5–40).
- Workflow execution UI showing the 6 stages with live progress messages.
- Exception list with filters (process, company code, vendor, risk, period) and CSV / Excel export.
- KPI-specific dashboard with summary tiles + Recharts (bar, pie, line, ageing table).
- Per-org persistence so a demo run can be revisited.

### Out of scope (v1, deferred)

- Real SAP / Oracle connection (the existing `Integrations` module covers this when the demo graduates to production).
- AI-generated explanations or remediation suggestions (recommendations are hardcoded per KPI; AI is a one-line swap later via `app.dma.services._azure_http`).
- Exception assignment / comments / case management.
- Custom KPI authoring UI (KPIs live in code).
- Scheduling / cron — runs are user-triggered.
- Multi-tenant data isolation beyond `org_id` scoping.

## 3. KPI / KRI Catalog (40 KPIs across 8 processes)

| # | Process | KPI | Rule pattern (§5) | Source tables |
|---|---------|-----|-------------------|---------------|
| 1 | Procurement | Duplicate Purchase Orders | `fuzzy_duplicate` | EKKO, EKPO |
| 2 | Procurement | PO Created After Invoice Date | `date_compare` | EKKO, RBKP |
| 3 | Procurement | Single Source Procurement | `aggregate_threshold` | EKKO, EKPO, LFA1 |
| 4 | Procurement | Contract Value Exceeding Approval Limit | `row_threshold` | EKKO |
| 5 | Procurement | Vendor Concentration | `aggregate_threshold` | EKKO, LFA1 |
| 6 | Procurement | PO Without Contract Reference | `missing_reference` | EKKO |
| 7 | Accounts Payable | Duplicate Invoice Payments | `fuzzy_duplicate` | RBKP, RSEG |
| 8 | Accounts Payable | Invoice Without Purchase Order | `missing_reference` | RBKP, EKKO |
| 9 | Accounts Payable | Three-Way Match Failures | `cross_table_compare` | RBKP, EKKO, EKPO |
| 10 | Accounts Payable | Round-Sum Invoice Amounts | `row_threshold` | RBKP |
| 11 | Accounts Payable | Payment to Inactive Vendor | `cross_table_compare` | RBKP, LFA1 |
| 12 | General Ledger | Manual Journal Entries Above Threshold | `row_threshold` | BKPF, BSEG |
| 13 | General Ledger | Posting on Weekend / Holiday | `temporal_anomaly` | BKPF |
| 14 | General Ledger | Round-Sum Journal Entries | `row_threshold` | BSEG |
| 15 | General Ledger | Reversal Journal Entries | `row_threshold` | BKPF |
| 16 | General Ledger | Maker = Checker (Same User Posting & Approving) | `cross_table_compare` | BKPF |
| 17 | Payroll | Duplicate Bank Account Across Employees | `fuzzy_duplicate` | PA0009 (Bank Details) |
| 18 | Payroll | Salary Change Without HR Approval | `missing_reference` | PA0008 (Basic Pay) |
| 19 | Payroll | Overtime Above Threshold | `row_threshold` | PA2002 (Attendances) |
| 20 | Payroll | Termination Without Final Settlement | `cross_table_compare` | PA0001, PA0008 |
| 21 | Inventory | Stock Adjustments Above Threshold | `row_threshold` | MSEG |
| 22 | Inventory | Negative Stock Balances | `row_threshold` | MARD |
| 23 | Inventory | Slow-Moving Inventory | `aggregate_threshold` | MSEG, MARA |
| 24 | Inventory | Inventory Write-offs by Same User | `aggregate_threshold` | MSEG |
| 25 | Inventory | Cycle Count Variances | `row_threshold` | MSEG |
| 26 | Sales / Revenue | Customer Credit Limit Exceeded | `cross_table_compare` | VBAK, KNKK |
| 27 | Sales / Revenue | Discount Above Threshold | `row_threshold` | VBAP |
| 28 | Sales / Revenue | Manual Sales Order Adjustments | `row_threshold` | VBAK |
| 29 | Sales / Revenue | Refunds Above Threshold | `row_threshold` | VBAK |
| 30 | Sales / Revenue | Revenue Recognition Anomalies | `temporal_anomaly` | VBRK |
| 31 | Access Management | Segregation of Duties Violations | `cross_table_compare` | AGR_USERS, AGR_1251 |
| 32 | Access Management | Inactive User Accounts (90+ days) | `temporal_anomaly` | USR02 |
| 33 | Access Management | Privileged Access Without Approval | `missing_reference` | USR02, AGR_USERS |
| 34 | Access Management | Multiple Failed Login Attempts | `aggregate_threshold` | USR02 |
| 35 | Access Management | Same User Creates and Approves | `cross_table_compare` | BKPF |
| 36 | Insurance / Operations | Claims Above Threshold | `row_threshold` | claims_master |
| 37 | Insurance / Operations | Multiple Claims Same Beneficiary | `aggregate_threshold` | claims_master, beneficiary_master |
| 38 | Insurance / Operations | Claim Without Supporting Documents | `missing_reference` | claims_master, claim_documents |
| 39 | Insurance / Operations | Claim Approval by Single User | `aggregate_threshold` | claims_master |
| 40 | Insurance / Operations | Aged Claims Pending Closure | `temporal_anomaly` | claims_master |

The KPI catalog lives in `backend/app/agents/cacm/kpi_catalog.py` as a list of `KpiDef` records (one row per line in the table above), so renaming / reordering is a one-file edit.

## 4. Hub Integration

### Catalog entry

Add to `backend/app/agents/__init__.py::CATALOG`:

```python
AgentDef(
    type="cacm",
    name="CACM",
    display_name="CACM",
    tagline="Continuous Audit & Continuous Monitoring",
    category="Compliance",
    icon="shield-check",
    implemented=True,
)
```

### Frontend routes

Mirror the `rca_investigation` model — explicit routes in `App.jsx`, full UI under a new directory:

| Route | Purpose |
|-------|---------|
| `/agents/cacm` | KPI Library landing |
| `/agents/cacm/run/:runId` | Live workflow execution |
| `/agents/cacm/runs/:runId/exceptions` | Exception list + export |
| `/agents/cacm/runs/:runId/dashboard` | Dashboard view |
| `/agents/cacm/runs` | History of past runs (this org) |

Sidebar entry: none — CACM appears as one more agent tile in the catalog. Users with the agent enabled and the right department membership see it.

### Org / department gating

Inherit from the existing agent gating. CACM is granted to an org via the platform super-admin agent-grant flow (`POST /api/platform/agents/grant`) — no new auth code.

## 5. Backend Architecture

### Directory layout

```
backend/app/agents/cacm/
├── __init__.py
├── kpi_catalog.py            # the 40 KpiDef records
├── recommendations.py         # hardcoded "Recommended action" text per KPI
├── service.py                 # pipeline orchestrator (the 6 stages)
├── rule_patterns/             # the seven reusable rule shapes
│   ├── __init__.py            # PATTERN_REGISTRY: name → callable
│   ├── row_threshold.py       # "value above X"
│   ├── fuzzy_duplicate.py     # similarity grouping (wraps dma/services/dedup_group_service)
│   ├── date_compare.py        # "date A > date B"
│   ├── aggregate_threshold.py # "groupby + sum/count > X"
│   ├── cross_table_compare.py # "join two tables, flag mismatch"
│   ├── missing_reference.py   # "row in A without matching row in B"
│   └── temporal_anomaly.py    # weekends, ageing, gaps
└── sample_data/
    ├── procurement.json       # EKKO + EKPO + LFA1 + RBKP + RSEG (engineered to trigger KPIs 1–6)
    ├── accounts_payable.json
    ├── general_ledger.json
    ├── payroll.json
    ├── inventory.json
    ├── sales_revenue.json
    ├── access_management.json
    └── insurance_ops.json
```

`backend/app/api/routes/cacm.py` — new FastAPI router mounted at `/api/cacm`, behind `require_org`.

### Rule pattern library — the key trick that makes 40 KPIs tractable

Most CACM-style rules are a small handful of shapes. Seven patterns cover all 40 KPIs in §3:

| Pattern | What it does | Example KPI |
|---------|--------------|-------------|
| `row_threshold` | Flag rows where `expr(row) compares value` | "Manual JE > $10k" |
| `fuzzy_duplicate` | Group near-duplicate rows by similarity over selected columns | "Duplicate POs" |
| `date_compare` | Flag rows where `date_a op date_b` | "PO date > Invoice date" |
| `aggregate_threshold` | Group rows, aggregate, flag groups crossing a threshold | "Vendor concentration > 50%" |
| `cross_table_compare` | Join two tables, flag rows that mismatch | "Payment to inactive vendor" |
| `missing_reference` | Anti-join: rows in A with no match in B | "PO without contract reference" |
| `temporal_anomaly` | Date-based: weekends, holidays, ageing buckets, gaps | "JE posted on weekend" |

Each pattern is a function `(ctx: RuleContext, params: dict) -> list[ExceptionRecord]`. A KPI in the catalog declares its pattern + params:

```python
KpiDef(
    type="po_after_invoice",
    process="Procurement",
    name="PO Created After Invoice Date",
    pattern="date_compare",
    params={
        "table": "ekko_with_invoice",      # logical table the orchestrator builds
        "left_date": "po_created",
        "right_date": "invoice_posted",
        "op": ">",
        "risk": {"diff_days": [(0, 3, "Low"), (4, 14, "Medium"), (15, None, "High")]},
        "exception_template": "PO {po_no} created {diff_days} days after invoice {inv_no} posted",
    },
)
```

Adding a new KPI = declare it. No bespoke Python.

### Run lifecycle

1. **POST `/api/cacm/runs`** with `{kpi_type}`:
   - Creates `CacmRun(status="running", ...)`.
   - Spawns `asyncio.create_task(_run_pipeline(run_id))`.
   - Returns `{run_id}` immediately.
2. The background task `_run_pipeline` walks the 6 stages, persisting events at each step and applying short `await asyncio.sleep(...)` delays between messages so the frontend has something to animate (~25 s total — long enough to demo, short enough to not lose attention).
3. On completion, sets `status="succeeded"`, fills `summary_json`, persists exceptions in `cacm_exceptions`.
4. On any exception, sets `status="failed"` with `error_message`.
5. **GET `/api/cacm/runs/{id}/events?since=N`** — returns events with `seq > N` (short-poll: the request returns immediately with whatever new events exist). Frontend polls every 500 ms until run status ≠ "running".

A run that's been in `status="running"` for longer than 5 minutes is considered stale (the background process probably crashed) and is auto-marked `failed` by a check the GET endpoint runs lazily. Avoids forever-spinning UIs.

### Database tables (one Alembic migration)

```
cacm_runs:
  id, org_id (FK), user_id (FK), kpi_type, process,
  status (running|succeeded|failed),
  started_at, completed_at,
  total_records, total_exceptions, exception_pct,
  summary_json (jsonb),
  error_message

cacm_run_events:
  id, run_id (FK), seq, stage, message, payload_json, ts

cacm_exceptions:
  id, run_id (FK), exception_no (e.g. "EX-0001"), risk, payload_json
```

Stored as JSON (instead of fully normalised columns) because each KPI has a different exception shape — fluffing this into a fixed schema right now is YAGNI given we have 40 different KPI shapes.

### Sample data

Per-process JSON files engineered so each KPI in that process produces 5–40 exceptions. Loaded into `pandas.DataFrame`s on each run (sub-100ms, no need to cache). Approximate volumes:

| Process | Approx rows |
|---------|-------------|
| Procurement | ~500 PO headers, ~600 invoices, ~80 vendors |
| Accounts Payable | ~700 invoices, ~80 vendors |
| General Ledger | ~1500 BSEG lines, ~600 BKPF docs |
| Payroll | ~250 employees |
| Inventory | ~400 materials, ~1200 movements |
| Sales / Revenue | ~600 sales orders, ~300 customers |
| Access Management | ~200 users, ~80 roles |
| Insurance / Operations | ~500 claims, ~250 beneficiaries |

Data is reused across runs (deterministic results — leadership demo always shows the same numbers).

## 6. Frontend Architecture

### Directory layout

```
frontend/src/cacm/
├── api.js                     # typed client wrapping fetch
├── pages/
│   ├── LibraryPage.jsx        # 8-process catalog, all KPIs live
│   ├── RunPage.jsx            # 6-stage stepper + live log
│   ├── ExceptionsPage.jsx     # filterable + exportable
│   ├── DashboardPage.jsx
│   └── RunsHistoryPage.jsx
└── components/
    ├── ProcessTile.jsx        # one of the 8 process tiles
    ├── KpiRow.jsx             # row inside a process tile
    ├── StageStepper.jsx       # 6-stage horizontal stepper
    ├── LogPanel.jsx           # terminal-style live log
    ├── ExceptionTable.jsx
    └── DashboardCharts.jsx
```

### Pages

#### LibraryPage (`/agents/cacm`)

- Header: "Continuous Audit & Continuous Monitoring" + tagline.
- 8 ProcessTile cards (3-column responsive). Each tile shows its KPI list with a green dot (all live in v1).
- Search / filter input across all KPIs.
- Click any KPI → POST `/runs` → navigate to RunPage with new `runId`.

#### RunPage (`/agents/cacm/run/:runId`)

- Top: KPI title + objective + parameters table.
- StageStepper: 6 numbered circles (Extract / Transform / Load / Rule Engine / Exceptions / Dashboard). Active stage animated.
- LogPanel: dark monospace, auto-scrolls. Lines append as events arrive.
- Polling hook: `useEvents(runId)` returns `{events, status}`; stops when status ≠ running.
- On `succeeded`: replace stepper with success banner + 2 CTA buttons "View Exceptions" and "View Dashboard".

#### ExceptionsPage (`/runs/:runId/exceptions`)

- Filter toolbar: process, company code, vendor (dropdown of distinct values from this run), risk (High / Med / Low), period.
- Table: all BR-specified columns. Risk badge colored. Clickable row → drawer with full payload + recommended action.
- Top-right: Download CSV / Download Excel.

#### DashboardPage (`/runs/:runId/dashboard`)

- 4 summary tiles: total records, total exceptions, exception %, open count.
- 2x2 chart grid (Recharts):
  - Bar: exceptions by company code
  - Pie: exceptions by risk category
  - Line: monthly trend (synthetic from sample data dates)
  - Bar: top recurring vendors / users / customers (depends on KPI domain)
- Bottom: Ageing of unresolved exceptions table.

### State

No global store. Each page fetches what it needs via `api.js`. `useEvents` is a small custom hook in `api.js`.

## 7. API Surface

All routes mounted under `/api/cacm` with `require_org` dependency.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/library` | All processes + KPIs (catalog) |
| POST | `/runs` body `{kpi_type}` | Start a run; returns `{run_id}` |
| GET | `/runs` query `kpi_type?` | List recent runs for this org |
| GET | `/runs/{id}` | Run summary (status, totals, summary_json) |
| GET | `/runs/{id}/events?since=N` | Short-poll for events |
| GET | `/runs/{id}/exceptions` query filters | List exceptions (filtered) |
| GET | `/runs/{id}/exceptions.csv` | CSV download |
| GET | `/runs/{id}/exceptions.xlsx` | Excel download (uses openpyxl, already a dep) |
| GET | `/runs/{id}/dashboard` | Aggregated dashboard data |

## 8. Testing Strategy

Following the project's existing patterns (`backend/tests/test_*.py`, monkeypatched, no live DB):

- `test_cacm_kpi_catalog.py` — every catalog entry has the required fields; no duplicate `type`s; all 8 processes covered; every KPI's `pattern` is registered in `PATTERN_REGISTRY`.
- `test_cacm_pattern_<name>.py` — one per pattern (7 files): golden tests with hand-crafted DataFrames → expected exceptions.
- `test_cacm_pipeline.py` — full orchestrator, asserts: (a) all 6 stages emit events in order, (b) exception counts roughly match expected ranges per KPI, (c) summary_json shape is valid for the dashboard.
- `test_cacm_routes.py` — FastAPI test client, override `require_org`: POST /runs → poll events → assert succeeded; CSV / Excel export endpoints return correct mimetypes and headers.
- **Per-KPI smoke test:** a parametrized test that runs each of the 40 KPIs end-to-end against its sample data and asserts (a) the run succeeds, (b) `total_exceptions` is in the expected range. Catches a misconfigured KPI declaration the moment someone adds one.

## 9. Migration & Rollback

- Single Alembic revision adds the 3 new tables. `alembic downgrade -1` cleanly removes them (foreign keys cascade).
- The agent CATALOG entry is code-only — no migration.
- Frontend changes are additive — no existing routes change.

## 10. Risks / Open Questions

- **Risk: 40 KPIs is a lot to hand-craft sample data for.** The rule-pattern library mitigates the *code* duplication, but each KPI still needs sample rows that trigger it convincingly. This is the dominant chunk of effort — about 30% of the build.
- **Risk: 6-stage animation timing.** Too fast (<10s) feels canned; too slow (>40s) loses attention. Target ~25s total with most time in the rule engine stage. Tuned during dev — spec doesn't pin specific delays.
- **Risk: Some exotic SAP table names** (PA0009, AGR_USERS, USR02) won't be familiar to leadership. The Library page tooltip on each KPI explains source tables in plain English, not just abbreviations.
- **Open:** Logo / icon for CACM in the agent tile. Use a generic `shield-check` from the existing icon set in v1.

## 11. Estimated effort

| Area | Effort |
|------|--------|
| KPI catalog + recommendations text (40 KPIs with full metadata) | 1 day |
| Sample data (8 process-level JSON files, hand-engineered) | 4 days |
| Rule-pattern library (7 patterns + tests) | 3 days |
| Backend service / orchestrator + routes + Alembic migration | 2 days |
| Frontend (5 pages + components) | 3 days |
| Per-KPI tuning (verify each KPI produces sensible exceptions) | 2 days |
| Polish / dev-and-demo loop | 1 day |
| **Total** | **~16 person-days** |

The pattern-library approach is what brings 40 KPIs down from ~30 days to ~16. Without it the per-KPI rule code would dominate; with it the per-KPI work is data + a config record.

## 12. Out-of-scope follow-ups

After v1 ships, natural next stories (each ~1–2 days):

1. **AI-generated remediation suggestions.** Each exception currently has a hardcoded recommended action; swap for an LLM call via `app.dma.services._azure_http.post_chat_completion` so suggestions are tailored to the specific exception.
2. **Exception assignment workflow** (assignee, status, comments, audit trail).
3. **Schedule a KPI to run on a cron** (uses scheduled-tasks integration, already in the hub).
4. **Real ERP integration** — wire SAP / Oracle EBS R12 (Oracle integration already exists) into the Extract stage instead of loading sample JSON.
5. **Custom KPI authoring UI** so org admins can add KPIs through the app instead of code.
