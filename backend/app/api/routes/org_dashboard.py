"""Org-admin dashboard — `GET /api/orgs/dashboard`.

Aggregates everything a single org's admin needs on their landing page:
per-agent usage, top members, runs over time, integrations health.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_org_admin, OrgContext
from app.models import Agent, AgentRun, Integration, Membership, User, UserAgent


router = APIRouter(prefix="/orgs", tags=["org-dashboard"])


@router.get("/dashboard")
def org_dashboard(
    ctx: OrgContext = Depends(require_org_admin),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    org_id = ctx.org_id

    # Counts
    member_count = (
        db.query(func.count(Membership.id))
        .filter(Membership.org_id == org_id, Membership.is_active.is_(True))
        .scalar() or 0
    )
    installed_agents = (
        db.query(func.count(Agent.id))
        .filter(Agent.org_id == org_id, Agent.is_enabled.is_(True))
        .scalar() or 0
    )
    total_runs = db.query(func.count(AgentRun.id)).filter(AgentRun.org_id == org_id).scalar() or 0
    runs_this_week = (
        db.query(func.count(AgentRun.id))
        .filter(AgentRun.org_id == org_id, AgentRun.created_at >= week_ago)
        .scalar() or 0
    )

    # Per-agent usage in this org.
    agent_rows = (
        db.query(Agent, func.count(AgentRun.id))
        .outerjoin(AgentRun, AgentRun.agent_id == Agent.id)
        .filter(Agent.org_id == org_id, Agent.is_enabled.is_(True))
        .group_by(Agent.id)
        .all()
    )
    agent_usage = []
    for agent, runs in agent_rows:
        pick_count = (
            db.query(func.count(UserAgent.id))
            .filter(UserAgent.agent_id == agent.id)
            .scalar() or 0
        )
        agent_usage.append({
            "agent_id": agent.id,
            "type": agent.type,
            "name": agent.name,
            "category": agent.category,
            "icon": agent.icon,
            "runs": runs or 0,
            "picked_by_users": pick_count,
        })
    agent_usage.sort(key=lambda a: a["runs"], reverse=True)

    # Top members by run count.
    top_users_rows = (
        db.query(User, func.count(AgentRun.id))
        .join(AgentRun, AgentRun.user_id == User.id)
        .filter(AgentRun.org_id == org_id)
        .group_by(User.id)
        .order_by(func.count(AgentRun.id).desc())
        .limit(8)
        .all()
    )
    top_users = [
        {"user_id": u.id, "name": u.name, "email": u.email, "runs": cnt}
        for u, cnt in top_users_rows
    ]

    # 30-day trend of runs in this org.
    per_day: dict[str, int] = {}
    rows = (
        db.query(AgentRun.created_at)
        .filter(AgentRun.org_id == org_id, AgentRun.created_at >= month_ago)
        .all()
    )
    for (ts,) in rows:
        if ts is None:
            continue
        key = (ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%d")
        per_day[key] = per_day.get(key, 0) + 1
    trend = [
        {"date": (now - timedelta(days=i)).strftime("%Y-%m-%d"),
         "count": per_day.get((now - timedelta(days=i)).strftime("%Y-%m-%d"), 0)}
        for i in range(29, -1, -1)
    ]

    # Integrations health.
    integrations = (
        db.query(Integration).filter(Integration.org_id == org_id).all()
    )
    integration_summary = [
        {"id": i.id, "type": i.type, "name": i.name, "status": i.status,
         "last_tested_at": i.last_tested_at.isoformat() if i.last_tested_at else None}
        for i in integrations
    ]

    # Recent runs. Resolve agent + user display names in two bulk queries
    # so the dashboard can render human-readable labels without N+1 round
    # trips. Raw ids stay on the payload for React keys / deep links.
    recent_rows = (
        db.query(AgentRun).filter(AgentRun.org_id == org_id)
        .order_by(AgentRun.created_at.desc()).limit(10).all()
    )
    needed_agent_ids = {r.agent_id for r in recent_rows if r.agent_id is not None}
    needed_user_ids = {r.user_id for r in recent_rows if r.user_id is not None}
    agent_name_by_id = (
        {a.id: a.name for a in db.query(Agent)
            .filter(Agent.id.in_(needed_agent_ids)).all()}
        if needed_agent_ids else {}
    )
    user_label_by_id = (
        {u.id: (u.name or u.email) for u in db.query(User)
            .filter(User.id.in_(needed_user_ids)).all()}
        if needed_user_ids else {}
    )
    recent = []
    for r in recent_rows:
        out = r.output or {}
        recent.append({
            "id": r.id,
            "agent_id": r.agent_id,
            "agent_name": agent_name_by_id.get(r.agent_id),
            "user_id": r.user_id,
            "user_name": user_label_by_id.get(r.user_id),
            "status": r.status,
            "coverage_pct": out.get("coverage_pct"),
            "phase": out.get("phase"),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })

    return {
        "org_id": org_id,
        "totals": {
            "members": member_count,
            "installed_agents": installed_agents,
            "runs": total_runs,
            "runs_this_week": runs_this_week,
        },
        "agent_usage": agent_usage,
        "top_users": top_users,
        "trend_30d": trend,
        "integrations": integration_summary,
        "recent_runs": recent,
    }
