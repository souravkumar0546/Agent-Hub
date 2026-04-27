# Uniqus Labs

A workspace where enterprise teams run AI agents on their data. Sixteen agents cover HR, Commercial, R&D, Procurement, Compliance, and Data Management. Role-based access, multi-tenant.

Built by integrating two internal tools — **DMAhub** (data transformation primitives) and **Devio** (investigation / deviation engine) — under a single product.

---

## Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy 2, PostgreSQL, JWT auth
- **Frontend:** React 18 + Vite, React Router
- **Design:** matches the `/docs/prototype.html` (unpacked from the Syngene standalone prototype)

## Folder layout

```
uniqus-ai-hub/
├── backend/                FastAPI — auth, RBAC, orgs, departments, agent APIs
│   └── app/
│       ├── agents/         catalog of 11 agent definitions
│       ├── api/            REST routes
│       ├── core/           config, database, JWT/bcrypt
│       ├── models/         SQLAlchemy models
│       ├── schemas/        Pydantic request/response models
│       └── seed/           idempotent bootstrap (Syngene org + depts + agents)
├── frontend/               Vite + React — shell, pages, design system
│   └── src/
│       ├── components/     Sidebar, TopBar, AppShell, AgentIcon, ProtectedRoute
│       ├── pages/          Login, AgentHub, AgentDetail, Knowledge, Runs
│       │   ├── admin/      Members, Departments, AuditLog
│       │   └── platform/   Orgs (super-admin only)
│       ├── lib/            API client + auth context
│       └── theme/          design tokens extracted from the prototype
└── docs/
    └── prototype.html      reference design
```

## Role model

| Tier   | Role          | Can do                                              |
|--------|---------------|-----------------------------------------------------|
| System | `SUPER_ADMIN` | Onboard orgs, platform config, cross-tenant view    |
| Org    | `ORG_ADMIN`   | Full control of one org — members, depts, audit     |
| Org    | `MEMBER`      | Use agents assigned to their depts, upload docs     |

Departments are **groupings**, not role tiers. An agent is visible to a member if the agent is assigned to one of the member's departments (or is org-wide).

## The 11 agents

1. Project Status
2. Meeting & MoM
3. HR Service
4. Hiring Visibility
5. Learning Journey (LMS)
6. Vendor Identification (parent-child)
7. R&D Material Visibility
8. Commercial Insights Chatbot
9. Molecule Pipeline Intelligence
10. 483 FDA Compliance
11. RCA / Investigation (from Devio)

## Running locally

### 1. Postgres

```bash
createdb syngene_hub
```

Or use Docker:

```bash
docker run -d --name syngene-pg -p 5432:5432 \
  -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=syngene_hub postgres:16
```

### 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit JWT_SECRET and bootstrap admin creds
uvicorn app.main:app --reload --port 8000
```

On first boot the seed creates:
- Org `Syngene Ltd` (slug `syngene`)
- 10 default departments
- All 11 agents, assigned to their default departments
- A SUPER_ADMIN user from `BOOTSTRAP_SUPER_ADMIN_EMAIL` / `_PASSWORD`

Swagger at http://localhost:8000/docs.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and sign in with the bootstrap super-admin credentials from your `backend/.env`.

## What's in this scaffold vs. next

**Done**
- Multi-tenant auth + RBAC (SUPER_ADMIN / ORG_ADMIN / MEMBER)
- Org, Department, Membership, Agent, AuditLog models
- Seed with Syngene + 11 agents
- Login → Agent Hub landing (11 tiles, gated by dept)
- Admin pages (Members / Departments / Audit), Platform page (Orgs)
- Design tokens + dark theme matching the prototype

**Next** (per agent)
- Flesh out each `app/agents/<type>/` with business logic
- Wire DMAhub primitives into the agents that need them (classify, dedupe, enrich, lookup, master-build)
- Port Devio's investigation engine into `app/agents/rca_investigation/`
- Knowledge Base upload + indexing
- Agent run dashboard with department-level usage analytics
- Orchestration / flow builder (from prototype screen at line 9647)
