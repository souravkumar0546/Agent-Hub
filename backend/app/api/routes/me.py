"""Per-user workspace routes — `/api/me/*`.

- `GET  /api/me/agents`         — agents in my workspace for the current org
- `POST /api/me/agents`         — pick an installed agent into my workspace
- `DELETE /api/me/agents/{id}`  — remove an agent from my workspace
- `GET  /api/me/dashboard`      — personal metrics for the landing page
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents import is_implemented
from app.api.deps import get_db, require_org, OrgContext
from app.models import Agent, AgentRun, AuditLog, UserAgent


router = APIRouter(prefix="/me", tags=["me"])


# ── Picks ────────────────────────────────────────────────────────────────────

class PickBody(BaseModel):
    agent_id: int


def _picked_rows(db: Session, ctx: OrgContext) -> list[tuple[UserAgent, Agent]]:
    """UserAgent + Agent rows for the user in the current org, enabled only."""
    return (
        db.query(UserAgent, Agent)
        .join(Agent, Agent.id == UserAgent.agent_id)
        .filter(
            UserAgent.user_id == ctx.user.id,
            UserAgent.org_id == ctx.org_id,
            Agent.is_enabled.is_(True),
        )
        .all()
    )


@router.get("/agents")
def list_my_agents(
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
):
    rows = _picked_rows(db, ctx)
    return [
        {
            "agent_id": a.id,
            "type": a.type,
            "name": a.name,
            "tagline": a.tagline,
            "category": a.category,
            "icon": a.icon,
            "implemented": is_implemented(a.type),
            "added_at": ua.added_at.isoformat() if ua.added_at else None,
            "is_pinned": ua.is_pinned,
        }
        for ua, a in rows
    ]


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def pick_agent(
    body: PickBody,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
):
    agent = db.get(Agent, body.agent_id)
    if agent is None or agent.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Agent not found in this org")
    if not agent.is_enabled:
        raise HTTPException(status_code=400, detail="Agent is not installed in this org")

    existing = (
        db.query(UserAgent)
        .filter(UserAgent.user_id == ctx.user.id, UserAgent.agent_id == agent.id)
        .one_or_none()
    )
    if existing is not None:
        return {"status": "already_picked", "agent_id": agent.id}

    db.add(UserAgent(
        user_id=ctx.user.id,
        org_id=ctx.org_id,
        agent_id=agent.id,
    ))
    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="me.agent_pick",
        target_type="agent",
        target_id=str(agent.id),
        meta={"agent_type": agent.type},
    ))
    db.commit()
    return {"status": "picked", "agent_id": agent.id}


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def unpick_agent(
    agent_id: int,
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
):
    row = (
        db.query(UserAgent)
        .filter(UserAgent.user_id == ctx.user.id, UserAgent.agent_id == agent_id)
        .one_or_none()
    )
    if row is None:
        return None
    db.delete(row)
    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="me.agent_unpick",
        target_type="agent",
        target_id=str(agent_id),
        meta={},
    ))
    db.commit()
    return None


# ── Personal dashboard ────────────────────────────────────────────────────

@router.get("/dashboard")
def my_dashboard(
    ctx: OrgContext = Depends(require_org),
    db: Session = Depends(get_db),
):
    """Metrics scoped to the current user in the current org."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    my_runs_q = db.query(AgentRun).filter(
        AgentRun.org_id == ctx.org_id,
        AgentRun.user_id == ctx.user.id,
    )
    total_runs = my_runs_q.count()
    runs_this_week = my_runs_q.filter(AgentRun.created_at >= week_ago).count()
    runs_this_month = my_runs_q.filter(AgentRun.created_at >= month_ago).count()

    picked = _picked_rows(db, ctx)

    # Per-picked-agent stats (scoped to me).
    agent_stats = []
    for ua, a in picked:
        rq = my_runs_q.filter(AgentRun.agent_id == a.id)
        count = rq.count()
        last = rq.order_by(AgentRun.created_at.desc()).first()
        agent_stats.append({
            "agent_id": a.id,
            "type": a.type,
            "name": a.name,
            "icon": a.icon,
            "runs": count,
            "last_used_at": last.created_at.isoformat() if last and last.created_at else None,
        })
    agent_stats.sort(key=lambda s: s["runs"], reverse=True)

    # Last 10 of my runs for the recent activity list.
    recent_rows = (
        my_runs_q.order_by(AgentRun.created_at.desc()).limit(10).all()
    )
    recent = []
    for r in recent_rows:
        out = r.output or {}
        recent.append({
            "id": r.id,
            "agent_id": r.agent_id,
            "status": r.status,
            "coverage_pct": out.get("coverage_pct"),
            "phase": out.get("phase"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "totals": {
            "picked_agents": len(picked),
            "total_runs": total_runs,
            "runs_this_week": runs_this_week,
            "runs_this_month": runs_this_month,
        },
        "agent_stats": agent_stats,
        "recent_runs": recent,
    }
