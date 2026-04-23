# Three-tier Agent Curation + Role-based Dashboards

> **For agentic workers:** Execute inline in this session (TDD/test-runner infra does not exist in this repo — we validate with smoke tests via curl + Vite compile checks). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the platform three levels of agent visibility — a platform catalog (library), per-org installed agents (curated by ORG_ADMIN), and per-user picked agents (MEMBER's workspace) — with a role-appropriate landing dashboard for each tier.

**Architecture:**
- Keep `CATALOG` in code as the platform-wide library source of truth.
- Reuse `Agent.is_enabled` to represent "installed in this org." Org admin toggles it.
- New `UserAgent` table represents "picked into my workspace." Member adds/removes.
- Three new dashboard endpoints (`/api/platform/dashboard`, `/api/orgs/dashboard`, `/api/me/dashboard`) return tier-appropriate aggregates.
- Role-based landing routing in `App.jsx`: super-admin → platform dashboard, org-admin → org dashboard, member → their workspace hub (already exists, now filtered to picked agents).

**Tech stack:** FastAPI + SQLAlchemy + Alembic on the backend; React Router + recharts on the frontend. No new dependencies.

---

## File map

### Backend
- **New:** `backend/app/models/user_agent.py` — `UserAgent` ORM class
- **Modify:** `backend/app/models/__init__.py` — export `UserAgent`
- **New:** `backend/alembic/versions/<rev>_add_user_agents.py` — migration
- **New:** `backend/app/api/routes/me.py` — `/api/me/*` routes for picks + dashboard
- **Modify:** `backend/app/api/routes/agents.py` — add catalog, install, enable/disable, filter by picks
- **Modify:** `backend/app/api/routes/platform.py` — expand `/stats` into a richer dashboard payload
- **New:** `backend/app/api/routes/org_dashboard.py` — `/api/orgs/dashboard`
- **Modify:** `backend/app/main.py` — register new routers
- **Modify:** `backend/app/schemas/common.py` — extend `AgentOut` with `is_installed` + `is_picked` flags

### Frontend
- **New:** `frontend/src/pages/PlatformDashboard.jsx`
- **New:** `frontend/src/pages/OrgDashboard.jsx`
- **New:** `frontend/src/pages/AgentLibraryPage.jsx`
- **Modify:** `frontend/src/pages/AgentHubPage.jsx` — becomes "My Agents" for members, full org view for admins
- **Modify:** `frontend/src/App.jsx` — role-based landing + new routes
- **Modify:** `frontend/src/components/Sidebar.jsx` — new "Agent Library" and role-aware "Dashboard" entries
- **Modify:** `frontend/src/lib/api.js` — no changes expected; existing helpers suffice

---

## Tasks

### Task 1: UserAgent model + migration

**Files:**
- Create: `backend/app/models/user_agent.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/<rev>_add_user_agents.py`

- [ ] **Step 1:** Create `UserAgent` ORM model with fields: `id`, `user_id` (FK users), `agent_id` (FK agents, cascade), `org_id` (FK orgs, cascade), `added_at`. UniqueConstraint on `(user_id, agent_id)`.
- [ ] **Step 2:** Export from `app/models/__init__.py`.
- [ ] **Step 3:** Run `alembic revision --autogenerate -m "add user_agents"` and review the generated file.
- [ ] **Step 4:** `alembic upgrade head`, verify table exists in Postgres.
- [ ] **Step 5:** Smoke-test: backend restarts cleanly.

### Task 2: Agent curation endpoints

**Files:**
- Modify: `backend/app/api/routes/agents.py`
- Modify: `backend/app/schemas/common.py`

- [ ] **Step 1:** Extend `AgentOut` with `is_installed: bool` (maps from `is_enabled`) and `is_picked: bool` (computed from `UserAgent`).
- [ ] **Step 2:** Add `GET /api/agents/catalog` — returns every entry in `CATALOG` as `{type, name, tagline, category, icon, implemented}`. Available to any authenticated user.
- [ ] **Step 3:** Add `POST /api/agents/install` — ORG_ADMIN only. Body `{type}`. If an `Agent` row for (org, type) exists and `is_enabled=False`, flip it on. If no row exists, create one with the catalog defaults (mirroring `_ensure_agents`).
- [ ] **Step 4:** Add `PATCH /api/agents/{id}` — ORG_ADMIN only. Body `{is_enabled}`. Flip the flag. Audit log.
- [ ] **Step 5:** Modify `GET /api/agents` to accept `?scope=installed|picked|all` (default `installed` for admins, `picked` for members). Return `is_installed` + `is_picked` on every row.
- [ ] **Step 6:** Smoke test via curl: install + disable + list.

### Task 3: Personal workspace endpoints

**Files:**
- Create: `backend/app/api/routes/me.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1:** Create `me.py` with router `/me`.
- [ ] **Step 2:** `GET /api/me/agents` — returns agents the current user has picked in the current org, with coverage/usage stats.
- [ ] **Step 3:** `POST /api/me/agents` — body `{agent_id}`. Validates the agent belongs to current org AND is_enabled. Creates `UserAgent` row (idempotent).
- [ ] **Step 4:** `DELETE /api/me/agents/{agent_id}` — removes the pick.
- [ ] **Step 5:** Register router in `main.py`.
- [ ] **Step 6:** Smoke test via curl: add + list + remove.

### Task 4: Three-tier dashboard endpoints

**Files:**
- Modify: `backend/app/api/routes/platform.py`
- Create: `backend/app/api/routes/org_dashboard.py`
- Modify: `backend/app/api/routes/me.py`

- [ ] **Step 1:** Replace `POST /api/platform/stats` with richer `GET /api/platform/dashboard` — totals + per-org activity + top agents platform-wide + recent runs across orgs + signup trend.
- [ ] **Step 2:** Create `GET /api/orgs/dashboard` — ORG_ADMIN+. Per-agent run counts for this org, top members by usage, runs over time, integrations health, member count.
- [ ] **Step 3:** Add `GET /api/me/dashboard` — for each picked agent: my run count, last used, my avg coverage (if applicable).
- [ ] **Step 4:** Register routers. Smoke test all three.

### Task 5: Platform Dashboard page (super admin)

**Files:**
- Create: `frontend/src/pages/PlatformDashboard.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1:** Build `PlatformDashboard.jsx`: tiles (orgs, users, memberships, agents-installed, total runs), org activity table with drill-into-org action, recent runs across orgs (last 10), top agents platform-wide bar chart, user signups trend line chart.
- [ ] **Step 2:** Sidebar: rename "Organizations" under Platform → "Dashboard" (keep Organizations as secondary link).
- [ ] **Step 3:** Route: `/platform/dashboard`. Super-admin landing becomes this (replaces current redirect to `/platform/orgs`).
- [ ] **Step 4:** Verify Vite compile + smoke test in browser.

### Task 6: Org Dashboard page (org admin)

**Files:**
- Create: `frontend/src/pages/OrgDashboard.jsx`
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`

- [ ] **Step 1:** Build `OrgDashboard.jsx`: tiles (members, installed agents, runs, completion), per-agent usage bar chart, top users table, runs over time line, integrations strip (connected/disconnected chips), recent runs list.
- [ ] **Step 2:** Sidebar: add "Dashboard" entry under Admin for org admins, above Members.
- [ ] **Step 3:** Route: `/admin/dashboard`. Org-admin landing becomes this.
- [ ] **Step 4:** Verify Vite compile + smoke test.

### Task 7: Agent Library page

**Files:**
- Create: `frontend/src/pages/AgentLibraryPage.jsx`
- Modify: `frontend/src/components/Sidebar.jsx`
- Modify: `frontend/src/App.jsx`

- [ ] **Step 1:** Build `AgentLibraryPage.jsx`: card grid pulling from `/api/agents/catalog`. Each card shows `{name, tagline, category, is_installed, is_picked, implemented}`. Button text depends on state + role:
  - Member + installed + not picked → `+ Add to my workspace`
  - Member + picked → `✓ In your workspace` (disabled or shows "Remove")
  - Member + not installed → `Not available in your org`
  - Admin + installed → `✓ Installed` + `Uninstall` button
  - Admin + not installed → `+ Install to org`
  - Not implemented → `Coming soon` (dimmed)
- [ ] **Step 2:** Add "Agent Library" to sidebar under Workspace.
- [ ] **Step 3:** Route `/library`.
- [ ] **Step 4:** Verify each button action triggers the right API call and updates UI.

### Task 8: Rework Agent Hub around picks

**Files:**
- Modify: `frontend/src/pages/AgentHubPage.jsx`

- [ ] **Step 1:** For **members**: Agent Hub loads `/api/agents?scope=picked`. If empty, show an empty state with "Browse the Agent Library to add agents to your workspace → /library".
- [ ] **Step 2:** Add a "+ Add more" inline CTA linking to `/library`.
- [ ] **Step 3:** For **org admins**: Agent Hub loads `/api/agents?scope=installed` (all installed, regardless of picks) so they see the full org config. Extra badge "INSTALLED" / "PICKED" per card.
- [ ] **Step 4:** Verify empty-state, populated-state, and admin-view all render correctly.

### Task 9: Role-based landing

**Files:**
- Modify: `frontend/src/App.jsx`
- Modify: `frontend/src/pages/AgentHubPage.jsx`

- [ ] **Step 1:** Wrap `/` with a role router component:
  - `user.is_super_admin && !viewingAsOrg` → Navigate `/platform/dashboard`
  - Current org role is `ORG_ADMIN` → Navigate `/admin/dashboard`
  - Otherwise → render `AgentHubPage` (member hub)
- [ ] **Step 2:** Remove the existing super-admin redirect from AgentHubPage — moved to the landing router.
- [ ] **Step 3:** Verify: each of the three existing users logs in and lands on the correct page.

### Task 10: Follow-up — production hardening (tracked, not executed now)

Listed here so we don't forget. Execute in a later session:

- Redis-backed rate limiter for the assistant (today it's in-memory; breaks under multi-instance deploys)
- Per-org DMA master storage on S3/Blob (today it's global on local disk)
- Pytest harness + a smoke-test suite covering auth, run-agent, dashboards
- Structured logging (JSON) + Sentry
- Dockerfile + docker-compose for prod; GitHub Actions for CI; Alembic upgrade as a release step
- Password reset + 2FA + session invalidation
- Knowledge Base upload wiring (UI exists as stub, no backend)
- DMAhub audit-log wiring (runs through `/api/dma/*` are not currently logged)

---

## Self-review

- **Spec coverage:** Every ask from the user message is covered:
  - "super admin should be able to add new orgs" → already exists, Task 5 surfaces it on the dashboard
  - "new orgs admin should be able to add and select which agent he wants" → Task 2 + Task 7
  - "user can also pick from agent library and those will go into his own my agent tabs" → Tasks 3, 7, 8
  - "super admin will see metrics according org wides dashboard (a left landing page after login)" → Tasks 4 + 5 + 9
  - "org admin will see how many people using which agent and all of metrics" → Tasks 4 + 6
  - "user will see metric from his agents" → Tasks 4 + 8
- **Placeholder scan:** No TODOs, no "similar to", no undefined functions.
- **Type consistency:** `is_installed` / `is_picked` used consistently across schema, list endpoint, library page.
- **Migration:** Alembic migration explicit in Task 1, upgrade step called out.
- **Test gap noted:** no pytest harness in repo; smoke tests via curl + Vite compile check serve as our verification gate. Real test suite is in Task 10 follow-ups.
