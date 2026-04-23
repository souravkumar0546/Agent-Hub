from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents import CATALOG, is_implemented
from app.api.deps import get_db, require_super_admin
from app.core.security import hash_password
from app.models import (
    Agent,
    AgentDepartment,
    AgentRun,
    AuditLog,
    Department,
    Membership,
    Organization,
    User,
)  # Department needed by /agents matrix payload; AuditLog for grant/revoke
from app.models.membership import OrgRole
from app.schemas.common import OrgOut
from app.schemas.validators import LogoUrl


router = APIRouter(prefix="/platform", tags=["platform"])


class OrgCreate(BaseModel):
    name: str
    slug: str
    admin_email: EmailStr
    admin_name: str
    admin_password: str
    # Validated + normalised via the shared LogoUrl annotation — rejects any
    # scheme that isn't http(s) to prevent stored XSS (see
    # `app.schemas.validators`). Empty / whitespace → None.
    logo_url: LogoUrl = None


class OrgWithStats(OrgOut):
    members: int = 0
    agents: int = 0
    runs: int = 0


@router.get("/orgs", response_model=list[OrgWithStats])
def list_orgs(_: User = Depends(require_super_admin), db: Session = Depends(get_db)):
    rows = db.query(Organization).order_by(Organization.name).all()

    # Bulk count in one query per stat, joined back into the list.
    mem_counts = dict(
        db.query(Membership.org_id, func.count(Membership.id))
        .filter(Membership.is_active.is_(True))
        .group_by(Membership.org_id)
        .all()
    )
    agent_counts = dict(
        db.query(Agent.org_id, func.count(Agent.id))
        .filter(Agent.is_enabled.is_(True))
        .group_by(Agent.org_id)
        .all()
    )
    run_counts = dict(
        db.query(AgentRun.org_id, func.count(AgentRun.id))
        .group_by(AgentRun.org_id)
        .all()
    )

    result = []
    for r in rows:
        base = OrgOut.model_validate(r).model_dump()
        result.append(OrgWithStats(
            **base,
            members=mem_counts.get(r.id, 0),
            agents=agent_counts.get(r.id, 0),
            runs=run_counts.get(r.id, 0),
        ))
    return result


@router.post("/orgs", response_model=OrgOut, status_code=status.HTTP_201_CREATED)
def create_org(
    payload: OrgCreate,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Provision a new org: org row + an ORG_ADMIN user.

    New orgs start **empty** — no departments, no agents. The platform super
    admin grants agents one at a time via POST /platform/agents/grant, and
    the org admin creates departments + installs the granted agents from the
    usual admin screens. This keeps the roles cleanly separated:

      - Super admin decides which agents an org has access to.
      - Org admin shapes the org (departments, which granted agents to install,
        department scoping).
    """
    if db.query(Organization).filter(Organization.slug == payload.slug).one_or_none():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="slug already exists")

    org = Organization(
        name=payload.name,
        slug=payload.slug,
        # Already validated + trimmed by the LogoUrl annotation (empty → None).
        logo_url=payload.logo_url,
    )
    db.add(org)
    db.flush()

    admin_email = payload.admin_email.lower()
    admin = db.query(User).filter(User.email == admin_email).one_or_none()
    if admin is None:
        admin = User(
            email=admin_email,
            name=payload.admin_name,
            password_hash=hash_password(payload.admin_password),
        )
        db.add(admin)
        db.flush()

    db.add(Membership(user_id=admin.id, org_id=org.id, role=OrgRole.ORG_ADMIN))
    db.commit()
    db.refresh(org)
    return OrgOut.model_validate(org)


@router.post("/stats")
def platform_stats(
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    return {
        "orgs": db.query(func.count(Organization.id)).scalar() or 0,
        "active_orgs": db.query(func.count(Organization.id)).filter(Organization.is_active.is_(True)).scalar() or 0,
        "users": db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0,
        "super_admins": db.query(func.count(User.id)).filter(User.is_super_admin.is_(True)).scalar() or 0,
        "memberships": db.query(func.count(Membership.id)).filter(Membership.is_active.is_(True)).scalar() or 0,
        "agents": db.query(func.count(Agent.id)).filter(Agent.is_enabled.is_(True)).scalar() or 0,
        "runs": db.query(func.count(AgentRun.id)).scalar() or 0,
    }


@router.get("/dashboard")
def platform_dashboard(
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Cross-org view for the super-admin landing page."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    month_ago = now - timedelta(days=30)

    totals = {
        "orgs": db.query(func.count(Organization.id)).scalar() or 0,
        "users": db.query(func.count(User.id)).filter(User.is_active.is_(True)).scalar() or 0,
        "memberships": db.query(func.count(Membership.id)).filter(Membership.is_active.is_(True)).scalar() or 0,
        "agents_installed": db.query(func.count(Agent.id)).filter(Agent.is_enabled.is_(True)).scalar() or 0,
        "runs": db.query(func.count(AgentRun.id)).scalar() or 0,
    }

    # Per-org activity summary.
    org_rows = db.query(Organization).order_by(Organization.name).all()
    mem_counts = dict(
        db.query(Membership.org_id, func.count(Membership.id))
        .filter(Membership.is_active.is_(True)).group_by(Membership.org_id).all()
    )
    agent_counts = dict(
        db.query(Agent.org_id, func.count(Agent.id))
        .filter(Agent.is_enabled.is_(True)).group_by(Agent.org_id).all()
    )
    run_counts = dict(
        db.query(AgentRun.org_id, func.count(AgentRun.id))
        .group_by(AgentRun.org_id).all()
    )
    orgs = [
        {
            "id": o.id,
            "name": o.name,
            "slug": o.slug,
            "is_active": o.is_active,
            "members": mem_counts.get(o.id, 0),
            "agents": agent_counts.get(o.id, 0),
            "runs": run_counts.get(o.id, 0),
        }
        for o in org_rows
    ]

    # Top agents platform-wide, grouped by type (same agent installed across
    # multiple orgs counts as one entry with summed runs).
    top_rows = (
        db.query(Agent.type, Agent.name, func.count(AgentRun.id))
        .outerjoin(AgentRun, AgentRun.agent_id == Agent.id)
        .filter(Agent.is_enabled.is_(True))
        .group_by(Agent.type, Agent.name)
        .order_by(func.count(AgentRun.id).desc())
        .limit(10)
        .all()
    )
    top_agents = [
        {"type": t, "name": n, "runs": cnt or 0}
        for t, n, cnt in top_rows
    ]

    # 30-day platform-wide runs trend.
    per_day: dict[str, int] = {}
    run_rows = (
        db.query(AgentRun.created_at)
        .filter(AgentRun.created_at >= month_ago).all()
    )
    for (ts,) in run_rows:
        if ts is None:
            continue
        key = (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%d")
        per_day[key] = per_day.get(key, 0) + 1
    trend = [
        {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
         "count": per_day.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
        for i in range(29, -1, -1)
    ]

    # Signups over the last 30 days.
    signup_rows = (
        db.query(User.created_at)
        .filter(User.is_active.is_(True), User.created_at >= month_ago).all()
    )
    per_day_signup: dict[str, int] = {}
    for (ts,) in signup_rows:
        if ts is None:
            continue
        key = (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%d")
        per_day_signup[key] = per_day_signup.get(key, 0) + 1
    signups_30d = [
        {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
         "count": per_day_signup.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
        for i in range(29, -1, -1)
    ]

    # Recent runs across every org — useful for spotting anomalies. We
    # resolve org and agent names server-side in two bulk lookups so the
    # UI can render human-readable labels without N+1 round-trips. (The
    # raw ids stay on the payload — the frontend uses them as React keys
    # and may still want them for deep links.)
    recent_rows = (
        db.query(AgentRun).order_by(AgentRun.created_at.desc()).limit(10).all()
    )
    needed_org_ids = {r.org_id for r in recent_rows}
    needed_agent_ids = {r.agent_id for r in recent_rows}
    org_name_by_id = (
        {o.id: o.name for o in db.query(Organization)
            .filter(Organization.id.in_(needed_org_ids)).all()}
        if needed_org_ids else {}
    )
    agent_name_by_id = (
        {a.id: a.name for a in db.query(Agent)
            .filter(Agent.id.in_(needed_agent_ids)).all()}
        if needed_agent_ids else {}
    )
    recent = []
    for r in recent_rows:
        out = r.output or {}
        recent.append({
            "id": r.id,
            "org_id": r.org_id,
            "org_name": org_name_by_id.get(r.org_id),
            "agent_id": r.agent_id,
            "agent_name": agent_name_by_id.get(r.agent_id),
            "status": r.status,
            "coverage_pct": out.get("coverage_pct"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "totals": totals,
        "orgs": orgs,
        "top_agents": top_agents,
        "trend_30d": trend,
        "signups_30d": signups_30d,
        "recent_runs": recent,
    }


# ── GET /api/platform/agents ──────────────────────────────────────────────
# Matrix view for the super-admin's Agent management page. Returns the
# platform catalog + every org + a list of installation records so the
# frontend can render a per-cell `(org, catalog_entry)` status without
# needing N separate calls.

@router.get("/agents")
def platform_agents_matrix(
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    # All orgs (name, slug, logo) for the column headers.
    org_rows = db.query(Organization).order_by(Organization.name).all()
    orgs = [
        {"id": o.id, "name": o.name, "slug": o.slug, "logo_url": o.logo_url}
        for o in org_rows
    ]

    # Platform catalog rows, sorted implemented-first then by display_name
    # (so the human-facing list order matches what the user sees on the card).
    catalog = [
        {
            "type": s.type,
            "name": s.name,
            "display_name": s.display_name or None,
            "tagline": s.tagline,
            "category": s.category,
            "icon": s.icon,
            "implemented": s.implemented,
        }
        for s in sorted(
            CATALOG,
            key=lambda s: (not s.implemented, (s.display_name or s.name).lower()),
        )
    ]

    # Every Agent row in the platform, joined with its department links.
    # We return `(org_id, agent_type, agent_id, is_enabled, department_ids)`
    # tuples — the frontend pivots them into the matrix cells.
    all_agents = db.query(Agent).all()
    # Bulk-fetch AgentDepartment rows in one query to avoid N+1.
    ad_rows = db.query(AgentDepartment).all()
    depts_by_agent: dict[int, list[int]] = {}
    for ad in ad_rows:
        depts_by_agent.setdefault(ad.agent_id, []).append(ad.department_id)

    # Each row exposes both permission bits — super admin's `granted_by_platform`
    # gate and the org admin's `is_enabled` install flag — so the matrix cell
    # can render the tri-state (not-granted / granted-idle / granted-installed)
    # plus the informational dept-scope chosen by the org admin.
    installations = [
        {
            "org_id": a.org_id,
            "agent_type": a.type,
            "agent_id": a.id,
            "granted_by_platform": a.granted_by_platform,
            "is_enabled": a.is_enabled,
            "department_ids": depts_by_agent.get(a.id, []),
        }
        for a in all_agents
    ]

    # Per-org department list — kept on the payload so the matrix can display
    # what scoping the org admin has picked without extra round trips.
    dept_rows = db.query(Department).order_by(Department.org_id, Department.name).all()
    departments_by_org: dict[int, list[dict]] = {}
    for d in dept_rows:
        departments_by_org.setdefault(d.org_id, []).append(
            {"id": d.id, "name": d.name, "slug": d.slug}
        )

    return {
        "orgs": orgs,
        "catalog": catalog,
        "installations": installations,
        "departments_by_org": departments_by_org,
    }


# ── Grant / revoke (super admin) ─────────────────────────────────────────────
# These are the ONLY knobs the super admin turns per (org, agent) cell. Super
# admins never touch `is_enabled` or department scope — that's the org admin's
# call. Grant creates (or re-enables) an Agent row in the target org so the org
# admin can see it on their Agent Library and decide whether to install.


class AgentGrantBody(BaseModel):
    org_id: int
    type: str


@router.post("/agents/grant", status_code=status.HTTP_200_OK)
def grant_agent(
    body: AgentGrantBody,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Grant a catalog agent to an org.

    - If no Agent row exists yet: create one with `granted_by_platform=True`,
      `is_enabled=False` — the agent now shows up in the org admin's library
      as "Available (not installed)".
    - If a row exists but was revoked (granted=False): flip it back to True.
      We do *not* auto-re-install — the org admin decides to install again
      explicitly. Department scoping (if any was previously set) is preserved
      because we never delete `AgentDepartment` rows on revoke.
    """
    spec = next((s for s in CATALOG if s.type == body.type), None)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {body.type}")
    if not db.get(Organization, body.org_id):
        raise HTTPException(status_code=404, detail="Organization not found")

    agent = (
        db.query(Agent)
        .filter(Agent.org_id == body.org_id, Agent.type == body.type)
        .one_or_none()
    )
    if agent is None:
        agent = Agent(
            org_id=body.org_id,
            type=spec.type,
            name=spec.name,
            tagline=spec.tagline,
            category=spec.category,
            icon=spec.icon,
            granted_by_platform=True,
            is_enabled=False,
            config={},
        )
        db.add(agent)
        db.flush()
        action = "platform.agent_grant"
    else:
        if agent.granted_by_platform:
            # Idempotent — just return the current state.
            return {
                "agent_id": agent.id,
                "org_id": agent.org_id,
                "type": agent.type,
                "granted_by_platform": True,
                "is_enabled": agent.is_enabled,
            }
        agent.granted_by_platform = True
        action = "platform.agent_regrant"

    db.add(AuditLog(
        org_id=body.org_id,
        user_id=None,  # platform-level action, not tied to an org membership
        action=action,
        target_type="agent",
        target_id=str(agent.id),
        meta={"agent_type": agent.type},
    ))
    db.commit()
    return {
        "agent_id": agent.id,
        "org_id": agent.org_id,
        "type": agent.type,
        "granted_by_platform": agent.granted_by_platform,
        "is_enabled": agent.is_enabled,
    }


@router.post("/agents/revoke", status_code=status.HTTP_200_OK)
def revoke_agent(
    body: AgentGrantBody,
    _: User = Depends(require_super_admin),
    db: Session = Depends(get_db),
):
    """Revoke a platform grant.

    Flips `granted_by_platform=False` AND forces `is_enabled=False` so members
    immediately lose access. The row is kept (not deleted) so `agent_runs` FKs
    survive and audit history stays intact; a future grant can re-enable it.
    Department scope rows are preserved — re-granting brings them back.
    """
    agent = (
        db.query(Agent)
        .filter(Agent.org_id == body.org_id, Agent.type == body.type)
        .one_or_none()
    )
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not granted to this org")

    agent.granted_by_platform = False
    agent.is_enabled = False
    db.add(AuditLog(
        org_id=body.org_id,
        user_id=None,
        action="platform.agent_revoke",
        target_type="agent",
        target_id=str(agent.id),
        meta={"agent_type": agent.type},
    ))
    db.commit()
    return {
        "agent_id": agent.id,
        "org_id": agent.org_id,
        "type": agent.type,
        "granted_by_platform": False,
        "is_enabled": False,
    }
