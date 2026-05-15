from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents import CATALOG, display_name_for, is_implemented, kind_for
from app.api.deps import get_db, require_org, require_org_admin, OrgContext
from app.models import Agent, AgentDepartment, AuditLog, Department, UserAgent
from app.schemas.common import AgentOut, CatalogAgentOut, IdName


router = APIRouter(prefix="/agents", tags=["agents"])


# Accepted values for the `kind` query filter. "all" / None = no filter.
KIND_FILTER_PATTERN = "^(agent|application|all)$"


# ── Helpers ──────────────────────────────────────────────────────────────────

def _picked_agent_ids(db: Session, user_id: int) -> set[int]:
    rows = db.query(UserAgent.agent_id).filter(UserAgent.user_id == user_id).all()
    return {r[0] for r in rows}


def _to_agent_out(agent: Agent, picked_ids: set[int]) -> AgentOut:
    # Include the department slug — the Agent Hub's dept-filter chips key off
    # it. Without it, chips render but filtering silently matches everything.
    depts = [
        IdName(id=ad.department.id, name=ad.department.name, slug=ad.department.slug)
        for ad in agent.departments
    ]
    return AgentOut(
        id=agent.id,
        type=agent.type,
        name=agent.name,
        # `display_name` is derived at serialization time from the code-side
        # CATALOG, not stored on the Agent row. This lets a rename in the
        # CATALOG propagate to every tenant on the next request without any
        # DB migration. Empty string ("") for an unknown type → None.
        display_name=display_name_for(agent.type) or None,
        tagline=agent.tagline,
        category=agent.category,
        icon=agent.icon,
        is_enabled=agent.is_enabled,
        is_installed=agent.is_enabled,
        is_picked=agent.id in picked_ids,
        implemented=is_implemented(agent.type),
        departments=depts,
        kind=kind_for(agent.type),
    )


# ── GET /api/agents ──────────────────────────────────────────────────────────

@router.get("", response_model=list[AgentOut])
def list_agents(
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
    department: str | None = Query(None, description="Filter by department slug (tag)"),
    scope: str = Query(
        "installed",
        pattern="^(installed|picked|all)$",
        description="installed = enabled in this org; picked = in my workspace; all = every Agent row",
    ),
    kind: str | None = Query(
        None,
        pattern=KIND_FILTER_PATTERN,
        description="Surface namespace filter — 'agent' or 'application'. Omit / 'all' = both.",
    ),
):
    """List agents in the org, scoped by `?scope=`:

    - `installed` (default): only agents the org admin has installed.
    - `picked`: only agents the current user has added to their personal workspace.
    - `all`: every Agent row — useful for admins browsing what's disabled.

    Optional `?kind=` restricts to one surface namespace (`agent` or
    `application`). The filter is applied post-query because the `kind`
    is derived from the in-process CATALOG, not stored on the DB row.
    """
    picked_ids = _picked_agent_ids(db, ctx.user.id)

    # Every scope respects the super-admin grant — a revoked agent must not
    # appear to members or org admins at all, even under `scope=all`. Only the
    # platform super admin sees the full picture (via /api/platform/agents).
    q = db.query(Agent).filter(
        Agent.org_id == ctx.org_id,
        Agent.granted_by_platform.is_(True),
    )
    if scope == "installed":
        q = q.filter(Agent.is_enabled.is_(True))
    elif scope == "picked":
        q = q.filter(Agent.is_enabled.is_(True), Agent.id.in_(picked_ids) if picked_ids else False)
    # `all` returns every granted row (installed + uninstalled) so the org
    # admin can toggle installs from a single page.
    agents = q.all()

    if department:
        dept = (
            db.query(Department)
            .filter(Department.org_id == ctx.org_id, Department.slug == department)
            .one_or_none()
        )
        if dept is None:
            return []
        agents = [a for a in agents if any(ad.department_id == dept.id for ad in a.departments)]

    if kind and kind != "all":
        agents = [a for a in agents if kind_for(a.type) == kind]

    # Implemented + alphabetical (matches existing UX).
    agents.sort(key=lambda a: (not is_implemented(a.type), a.name.lower()))
    return [_to_agent_out(a, picked_ids) for a in agents]


# ── GET /api/agents/catalog ─────────────────────────────────────────────────
#
# Returns the platform-wide library. Each entry is annotated with whether it
# is installed in the current user's org and whether the current user has
# picked it — the Agent Library page uses this to render role-appropriate
# action buttons.

@router.get("/catalog", response_model=list[CatalogAgentOut])
def agent_catalog(
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
    kind: str | None = Query(
        None,
        pattern=KIND_FILTER_PATTERN,
        description="Surface namespace filter — 'agent' or 'application'. Omit / 'all' = both.",
    ),
):
    """Org-admin / member catalog view.

    Only returns agents that the platform super admin has granted to this org.
    Ungranted catalog entries are deliberately invisible here — the super
    admin's grant page is where those live. This keeps the org admin's Agent
    Library focused on what they can actually control (install + dept scope).
    """
    # Map every *granted* org-Agent row by type. Revoked rows are filtered out
    # so the org admin doesn't see ghosted catalog entries for agents they're
    # no longer allowed to use.
    installed_by_type: dict[str, Agent] = {
        a.type: a
        for a in (
            db.query(Agent)
            .filter(Agent.org_id == ctx.org_id, Agent.granted_by_platform.is_(True))
            .all()
        )
    }
    picked_ids = _picked_agent_ids(db, ctx.user.id)

    result: list[CatalogAgentOut] = []
    for spec in CATALOG:
        if kind and kind != "all" and spec.kind != kind:
            continue
        agent = installed_by_type.get(spec.type)
        if agent is None:
            # Not granted — hide entirely.
            continue
        result.append(CatalogAgentOut(
            type=spec.type,
            name=spec.name,
            display_name=spec.display_name or None,
            tagline=spec.tagline,
            category=spec.category,
            icon=spec.icon,
            implemented=spec.implemented,
            is_installed=bool(agent.is_enabled),
            is_picked=bool(agent.id in picked_ids),
            agent_id=agent.id,
            kind=spec.kind,
        ))
    # Sort: implemented first, then alphabetical.
    result.sort(key=lambda e: (not e.implemented, e.name.lower()))
    return result


# ── POST /api/agents/install (ORG_ADMIN) ─────────────────────────────────────

class InstallBody(BaseModel):
    type: str
    # Optional — restrict this agent to specific departments. Empty list or
    # omitted = inherit the catalog defaults (typically the legacy behaviour).
    department_ids: list[int] | None = None


def _apply_department_ids(
    db: Session,
    agent: Agent,
    org_id: int,
    department_ids: list[int],
) -> list[int]:
    """Replace an agent's department links with the given set.

    Silently drops IDs that don't belong to the agent's org so a malicious or
    mistaken payload can't cross tenants. Returns the applied IDs.
    """
    valid_ids = [
        d.id for d in (
            db.query(Department)
            .filter(Department.org_id == org_id, Department.id.in_(department_ids))
            .all()
        )
    ]
    db.query(AgentDepartment).filter(AgentDepartment.agent_id == agent.id).delete()
    db.flush()
    for did in valid_ids:
        db.add(AgentDepartment(agent_id=agent.id, department_id=did))
    return valid_ids


@router.post("/install", response_model=AgentOut, status_code=status.HTTP_201_CREATED)
def install_agent(
    body: InstallBody,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    """Install a granted agent — org admin's install gate.

    Requires the platform super admin to have granted the agent first
    (POST /platform/agents/grant creates the Agent row). Calling install on
    an ungranted catalog entry returns 403.

    `department_ids` optionally restricts visibility to specific departments
    (members outside those depts won't see it in their workspace). Omit or
    pass an empty list for org-wide visibility.
    """
    spec = next((s for s in CATALOG if s.type == body.type), None)
    if spec is None:
        raise HTTPException(status_code=400, detail=f"Unknown agent type: {body.type}")

    agent = (
        db.query(Agent)
        .filter(Agent.org_id == ctx.org_id, Agent.type == body.type)
        .one_or_none()
    )
    if agent is None or not agent.granted_by_platform:
        raise HTTPException(
            status_code=403,
            detail=(
                "This agent has not been granted to your organisation yet. "
                "Ask your platform administrator to enable it."
            ),
        )
    if agent.is_enabled:
        raise HTTPException(status_code=409, detail="Agent already installed")

    agent.is_enabled = True
    action = "agent.install"
    if body.department_ids is not None:
        _apply_department_ids(db, agent, ctx.org_id, body.department_ids)

    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action=action,
        target_type="agent",
        target_id=str(agent.id),
        meta={"agent_type": spec.type, "department_ids": body.department_ids or []},
    ))
    db.commit()
    db.refresh(agent)
    return _to_agent_out(agent, _picked_agent_ids(db, ctx.user.id))


# ── PATCH /api/agents/{id} (ORG_ADMIN) ──────────────────────────────────────

class AgentPatch(BaseModel):
    is_enabled: bool | None = None
    # Pass a list to replace the agent's dept scoping; omit to leave alone.
    department_ids: list[int] | None = None


@router.patch("/{agent_id}", response_model=AgentOut)
def patch_agent(
    agent_id: int,
    body: AgentPatch,
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    agent = db.get(Agent, agent_id)
    if agent is None or agent.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Agent not found")

    if body.is_enabled is not None and agent.is_enabled != body.is_enabled:
        old = agent.is_enabled
        agent.is_enabled = body.is_enabled
        db.add(AuditLog(
            org_id=ctx.org_id,
            user_id=ctx.user.id,
            action="agent.uninstall" if old else "agent.reinstall",
            target_type="agent",
            target_id=str(agent.id),
            meta={"agent_type": agent.type, "is_enabled": body.is_enabled},
        ))

    if body.department_ids is not None:
        applied = _apply_department_ids(db, agent, ctx.org_id, body.department_ids)
        db.add(AuditLog(
            org_id=ctx.org_id,
            user_id=ctx.user.id,
            action="agent.departments_update",
            target_type="agent",
            target_id=str(agent.id),
            meta={"agent_type": agent.type, "department_ids": applied},
        ))

    db.commit()
    db.refresh(agent)
    return _to_agent_out(agent, _picked_agent_ids(db, ctx.user.id))
