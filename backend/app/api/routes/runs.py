"""Agent-run endpoints — run an agent, list runs, fetch a run, export DOCX.

Route layout:
  POST   /api/agents/{agent_id}/run         — run the agent (multipart: message + files)
  GET    /api/agents/{agent_id}/runs        — list runs for this agent (current user)
  GET    /api/runs/{run_id}                 — fetch one run
  GET    /api/runs/{run_id}/export.docx     — export the run output as a DOCX (Investigation only)

Dispatch is type-driven: the Agent's `type` string maps to the module under
`app.agents.<type>` which must expose an async `run(**kwargs)` coroutine.
"""

from __future__ import annotations

import importlib
import time
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session as DbSession

from app.api.deps import get_db, require_org, OrgContext
from app.models import Agent, AgentRun, AuditLog


# Separate router so `/api/runs/...` paths don't need the `/agents` prefix.
runs_router = APIRouter(prefix="/runs", tags=["runs"])
agent_runs_router = APIRouter(prefix="/agents", tags=["runs"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_agent(db: DbSession, org_id: int, agent_id: int) -> Agent:
    agent = (
        db.query(Agent)
        .filter(Agent.id == agent_id, Agent.org_id == org_id, Agent.is_enabled.is_(True))
        .one_or_none()
    )
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
    return agent


def _run_out(run: AgentRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "agent_id": run.agent_id,
        "parent_run_id": run.parent_run_id,
        "user_id": run.user_id,
        "status": run.status,
        "duration_ms": run.duration_ms,
        "error": run.error,
        "input": run.input,
        "output": run.output,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


async def _extract_attachments(files: list[UploadFile]) -> tuple[str, list[dict]]:
    """Run uploaded files through the Investigation file extractor (PDF/DOCX/DOC/TXT).

    Returns (concatenated_text_block, metadata_list).
    """
    if not files:
        return "", []

    # Lazy import so agents that don't need extraction aren't forced to load it.
    from app.agents.rca_investigation.file_extractor import extract_uploaded_file

    ALLOWED = {".pdf", ".doc", ".docx", ".txt", ".csv", ".log"}
    MAX_FILE_SIZE = 10 * 1024 * 1024

    chunks: list[str] = []
    meta: list[dict] = []

    for f in files:
        name = f.filename or ""
        ext = "." + name.rsplit(".", 1)[-1].lower() if "." in name else ""
        if ext not in ALLOWED:
            continue
        filename, text = await extract_uploaded_file(f)
        if text and not text.startswith("[Unsupported"):
            truncated = text[:15000]  # protect LLM context
            chunks.append(f"[Attached file: {filename}]\n{truncated}")
            meta.append({
                "filename": filename,
                "size": f.size or 0,
                "content_type": f.content_type or "",
            })

    return ("\n\n---\n\n".join(chunks), meta)


def _write_audit(db: DbSession, *, ctx: OrgContext, run: AgentRun, agent_type: str, status_label: str) -> None:
    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="agent.run",
        target_type="agent_run",
        target_id=str(run.id),
        meta={"agent_type": agent_type, "status": status_label, "duration_ms": run.duration_ms},
    ))
    db.commit()


# ── POST /api/agents/{id}/run ────────────────────────────────────────────────

@agent_runs_router.post("/{agent_id}/run")
async def run_agent(
    agent_id: int,
    message: str = Form(""),
    parent_run_id: int | None = Form(None),
    files: list[UploadFile] = File(default=[]),
    ctx: OrgContext = Depends(require_org),
    db: DbSession = Depends(get_db),
):
    """Run an agent. Multipart body: `message`, optional `parent_run_id`, optional `files[]`.

    Any org member can run any agent (dept tags are informational, not gating).
    """
    agent = _get_agent(db, ctx.org_id, agent_id)

    # Extract file contents up-front (before we record the run, so we have metadata)
    attachments_text, attachments_meta = await _extract_attachments(files or [])

    if not message.strip() and not attachments_text:
        raise HTTPException(status_code=400, detail="message or files required")

    # If a parent_run_id is provided, validate it belongs to the same agent + org
    prior_session: dict | None = None
    if parent_run_id is not None:
        parent = db.get(AgentRun, parent_run_id)
        if (
            parent is None
            or parent.org_id != ctx.org_id
            or parent.agent_id != agent_id
        ):
            raise HTTPException(status_code=400, detail="Invalid parent_run_id")
        prior_session = (parent.output or {}).get("session")

    run = AgentRun(
        org_id=ctx.org_id,
        agent_id=agent.id,
        user_id=ctx.user.id,
        parent_run_id=parent_run_id,
        status="running",
        input={
            "message": message,
            "attachments_meta": attachments_meta,
            "attachments_text_len": len(attachments_text),
            "parent_run_id": parent_run_id,
        },
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Resolve agent module + dispatch
    try:
        module = importlib.import_module(f"app.agents.{agent.type}")
    except ImportError as e:
        run.status = "failed"
        run.error = f"Agent module not installed: {e}"
        db.commit()
        _write_audit(db, ctx=ctx, run=run, agent_type=agent.type, status_label="failed")
        raise HTTPException(status_code=501, detail=f"Agent '{agent.type}' not implemented")

    if not hasattr(module, "run"):
        run.status = "failed"
        run.error = "Agent module has no `run` coroutine"
        db.commit()
        _write_audit(db, ctx=ctx, run=run, agent_type=agent.type, status_label="failed")
        raise HTTPException(status_code=501, detail=f"Agent '{agent.type}' has no run() entry point")

    started = time.time()
    try:
        output = await module.run(
            owner_name=ctx.user.name,
            owner_employee_id="",  # not modelled in User yet
            owner_department="",
            input_dict={
                "message": message,
                "attachments_text": attachments_text,
                "attachments_meta": attachments_meta,
            },
            prior_session_dict=prior_session,
        )
    except Exception as e:
        run.status = "failed"
        run.error = str(e)[:2000]
        run.duration_ms = int((time.time() - started) * 1000)
        db.commit()
        _write_audit(db, ctx=ctx, run=run, agent_type=agent.type, status_label="failed")
        raise HTTPException(status_code=500, detail=f"Agent run failed: {e}")

    run.status = "completed"
    run.output = output
    run.duration_ms = int((time.time() - started) * 1000)
    db.commit()
    db.refresh(run)

    _write_audit(db, ctx=ctx, run=run, agent_type=agent.type, status_label="ok")
    return _run_out(run)


# ── GET /api/agents/{id}/runs ────────────────────────────────────────────────

@agent_runs_router.get("/{agent_id}/runs")
def list_agent_runs(
    agent_id: int,
    limit: int = 50,
    ctx: OrgContext = Depends(require_org),
    db: DbSession = Depends(get_db),
):
    _get_agent(db, ctx.org_id, agent_id)

    # SQLAlchemy forbids `.filter()` after `.limit()`. Apply every filter
    # (including the member-scope one) before ordering / limiting.
    q = db.query(AgentRun).filter(
        AgentRun.org_id == ctx.org_id,
        AgentRun.agent_id == agent_id,
    )
    # Members only see their own runs; org admins / super admins see all.
    if not ctx.is_org_admin:
        q = q.filter(AgentRun.user_id == ctx.user.id)

    q = q.order_by(AgentRun.created_at.desc()).limit(limit)

    # Trim the heavy `output` field when listing — a summary is enough.
    rows = q.all()

    # Compute a per-org sequence number for each chain root. Shown to users
    # instead of the global AgentRun.id, which is a platform-wide auto-
    # increment and feels confusing ("my first Uniqus run is #15?").
    root_id_list = [
        rid for (rid,) in (
            db.query(AgentRun.id)
            .filter(
                AgentRun.org_id == ctx.org_id,
                AgentRun.agent_id == agent_id,
                AgentRun.parent_run_id.is_(None),
            )
            .order_by(AgentRun.created_at.asc(), AgentRun.id.asc())
            .all()
        )
    ]
    root_seq: dict[int, int] = {rid: i + 1 for i, rid in enumerate(root_id_list)}

    def _preview(r: AgentRun) -> str | None:
        msg = (r.input or {}).get("message") or ""
        if msg:
            return msg[:140]
        # Fall back to the first user message in the session (useful for
        # child runs in a chain whose `input.message` may be empty on edits).
        msgs = ((r.output or {}).get("session") or {}).get("messages") or []
        for m in msgs:
            if m.get("role") == "user" and m.get("content"):
                return m["content"][:140]
        return None

    def _investigation_no(r: AgentRun) -> int | None:
        # For chain roots this is the per-org sequence number (1 = first
        # investigation ever run in this org/agent). For child turns we
        # resolve to the root's number so the UI can label every row by
        # its conversation, not by its raw global id.
        root_id = r.id if r.parent_run_id is None else r.parent_run_id
        # Walk up in case of deep chains (cheap — chain depth is bounded by
        # the number of turns, typically 1–3).
        seen = {root_id}
        while True:
            seq = root_seq.get(root_id)
            if seq is not None:
                return seq
            parent = db.get(AgentRun, root_id)
            if parent is None or parent.parent_run_id is None or parent.parent_run_id in seen:
                return None
            root_id = parent.parent_run_id
            seen.add(root_id)

    return [
        {
            "id": r.id,
            "investigation_no": _investigation_no(r),
            "agent_id": r.agent_id,
            "parent_run_id": r.parent_run_id,
            "user_id": r.user_id,
            "status": r.status,
            "duration_ms": r.duration_ms,
            "coverage_pct": (r.output or {}).get("coverage_pct") if r.output else None,
            "phase": (r.output or {}).get("phase") if r.output else None,
            "preview": _preview(r),
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]


# ── GET /api/agents/{id}/stats ───────────────────────────────────────────────

@agent_runs_router.get("/{agent_id}/stats")
def agent_stats(
    agent_id: int,
    ctx: OrgContext = Depends(require_org),
    db: DbSession = Depends(get_db),
):
    """Dashboard metrics for one agent, scoped to the org.

    Members see stats over their own runs only; org admins see everything.
    Numbers are computed from `AgentRun.output` fields so no new schema
    is required. Kept deliberately simple — one pass over the rows.
    """
    from datetime import datetime, timedelta, timezone
    import re

    q = db.query(AgentRun).filter(
        AgentRun.org_id == ctx.org_id,
        AgentRun.agent_id == agent_id,
    )
    if not ctx.is_org_admin:
        q = q.filter(AgentRun.user_id == ctx.user.id)
    rows = q.all()

    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    month_start = now - timedelta(days=30)
    prev_week_start = now - timedelta(days=14)
    prev_month_start = now - timedelta(days=60)

    # Treat each parent_run_id=None row as a distinct "investigation".
    # Runs descended from it (AI turns or field edits) are follow-ups.
    investigations = [r for r in rows if r.parent_run_id is None]
    followups_by_root: dict[int, list] = {}
    for r in rows:
        if r.parent_run_id is None:
            continue
        # Walk back to the root for chain attribution.
        cur = r
        while cur.parent_run_id is not None:
            parent = next((x for x in rows if x.id == cur.parent_run_id), None)
            if parent is None:
                break
            cur = parent
        followups_by_root.setdefault(cur.id, []).append(r)

    def _aware(dt):
        # SQLAlchemy can return naive datetimes depending on driver config —
        # normalize so comparisons with `now` (tz-aware) don't blow up.
        if dt is None:
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    # ── core counters ────────────────────────────────────────────────
    total = len(investigations)
    this_week = sum(1 for r in investigations if _aware(r.created_at) and _aware(r.created_at) >= week_start)
    prev_week = sum(1 for r in investigations if _aware(r.created_at) and prev_week_start <= _aware(r.created_at) < week_start)
    this_month = sum(1 for r in investigations if _aware(r.created_at) and _aware(r.created_at) >= month_start)
    prev_month = sum(1 for r in investigations if _aware(r.created_at) and prev_month_start <= _aware(r.created_at) < month_start)

    # Latest run in each chain (what "current state" looks like).
    def _chain_latest(root: AgentRun) -> AgentRun:
        kids = followups_by_root.get(root.id, [])
        return max(kids, key=lambda r: r.id) if kids else root

    latest_per_chain = [_chain_latest(r) for r in investigations]

    def _coverage(r):
        return (r.output or {}).get("coverage_pct") or 0.0

    def _phase(r):
        return (r.output or {}).get("phase") or "intake"

    coverages = [float(_coverage(r)) for r in latest_per_chain]
    avg_coverage = round(sum(coverages) / len(coverages), 1) if coverages else 0.0

    # Duration stats on AI turns only (user-edit turns have duration_ms=0).
    ai_runs = [r for r in rows if r.duration_ms and r.duration_ms > 0]
    avg_duration = round(sum(r.duration_ms for r in ai_runs) / len(ai_runs)) if ai_runs else 0

    # Completion rate = latest chain state reached `review` with >=90% coverage.
    completed = sum(
        1 for r in latest_per_chain
        if _phase(r) == "review" and float(_coverage(r)) >= 90
    )
    completion_rate = round(completed / total * 100, 1) if total else 0.0

    # Phase distribution across current state.
    phase_dist: dict[str, int] = {}
    for r in latest_per_chain:
        phase_dist[_phase(r)] = phase_dist.get(_phase(r), 0) + 1

    # Coverage histogram (10-pt buckets).
    buckets = [0] * 10  # 0-10, 10-20, ..., 90-100
    for c in coverages:
        idx = min(int(c // 10), 9)
        buckets[idx] += 1
    coverage_histogram = [
        {"bucket": f"{i*10}-{i*10+10}%", "count": buckets[i]}
        for i in range(10)
    ]

    # 30-day trend: investigations created per day.
    per_day: dict[str, int] = {}
    for r in investigations:
        c = _aware(r.created_at)
        if not c or c < month_start:
            continue
        key = c.strftime("%Y-%m-%d")
        per_day[key] = per_day.get(key, 0) + 1
    trend = []
    for i in range(29, -1, -1):
        day = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append({"date": day, "count": per_day.get(day, 0)})

    # Follow-up behaviour: percentage of chains with more than one turn,
    # and average turns per investigation (counting every AI + edit run).
    turns_per_chain = [1 + len(followups_by_root.get(r.id, [])) for r in investigations]
    avg_turns = round(sum(turns_per_chain) / len(turns_per_chain), 1) if turns_per_chain else 0.0
    multi_turn_pct = round(
        sum(1 for t in turns_per_chain if t > 1) / len(turns_per_chain) * 100, 1
    ) if turns_per_chain else 0.0

    # Department with most deviations (from the initiating user's department —
    # we don't track that on User yet, so fall back to the agent's own tags).
    dept_counts: dict[str, int] = {}
    for r in investigations:
        if r.department_id is None:
            continue
        dept_counts[str(r.department_id)] = dept_counts.get(str(r.department_id), 0) + 1
    # Resolve dept IDs → names.
    from app.models import Department
    if dept_counts:
        depts = db.query(Department).filter(Department.id.in_([int(k) for k in dept_counts])).all()
        name_by_id = {str(d.id): d.name for d in depts}
        top_departments = sorted(
            [{"department": name_by_id.get(k, k), "count": v} for k, v in dept_counts.items()],
            key=lambda x: -x["count"],
        )[:5]
    else:
        top_departments = []

    # SOP references — pull strings like "SOP-GMP-QA-0066" from any field value.
    sop_pattern = re.compile(r"\bSOP-[A-Z]+-[A-Z]+-\d{3,5}\b")
    sop_counts: dict[str, int] = {}
    for r in latest_per_chain:
        fields = (r.output or {}).get("session", {}).get("fields", {})
        for f in fields.values():
            value = (f or {}).get("value") or ""
            for match in sop_pattern.findall(value):
                sop_counts[match] = sop_counts.get(match, 0) + 1
    top_sops = sorted(
        [{"sop": k, "count": v} for k, v in sop_counts.items()],
        key=lambda x: -x["count"],
    )[:5]

    # Weekly success-rate trend over the last 6 weeks.
    weekly = []
    for w in range(5, -1, -1):
        w_start = now - timedelta(days=(w + 1) * 7)
        w_end = now - timedelta(days=w * 7)
        chains_in_week = [r for r in investigations if _aware(r.created_at) and w_start <= _aware(r.created_at) < w_end]
        if not chains_in_week:
            weekly.append({"week": w_end.strftime("%d %b"), "total": 0, "completed": 0, "rate": 0.0})
            continue
        latest = [_chain_latest(r) for r in chains_in_week]
        done = sum(1 for r in latest if _phase(r) == "review" and float(_coverage(r)) >= 90)
        weekly.append({
            "week": w_end.strftime("%d %b"),
            "total": len(chains_in_week),
            "completed": done,
            "rate": round(done / len(chains_in_week) * 100, 1),
        })

    def _delta(cur, prev):
        if prev == 0:
            return None if cur == 0 else 100.0
        return round((cur - prev) / prev * 100, 1)

    return {
        "totals": {
            "investigations": total,
            "this_week": this_week,
            "this_month": this_month,
            "prev_week": prev_week,
            "prev_month": prev_month,
            "week_delta_pct": _delta(this_week, prev_week),
            "month_delta_pct": _delta(this_month, prev_month),
        },
        "averages": {
            "coverage_pct": avg_coverage,
            "duration_ms": avg_duration,
            "turns_per_investigation": avg_turns,
            "multi_turn_pct": multi_turn_pct,
        },
        "completion_rate": completion_rate,
        "phase_distribution": [
            {"phase": k, "count": v} for k, v in phase_dist.items()
        ],
        "coverage_histogram": coverage_histogram,
        "trend_30d": trend,
        "weekly_success_rate": weekly,
        "top_departments": top_departments,
        "top_sops": top_sops,
    }


# ── GET /api/runs/{run_id} ───────────────────────────────────────────────────

@runs_router.get("/{run_id}")
def get_run(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: DbSession = Depends(get_db),
):
    run = db.get(AgentRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Run not found")
    if not ctx.is_org_admin and run.user_id != ctx.user.id:
        raise HTTPException(status_code=403, detail="Not your run")
    return _run_out(run)


# ── PATCH /api/runs/{run_id}/fields/{field_id} ──────────────────────────────
# Inline field edits from the live template preview. Creates a new AgentRun
# child of the given run, with the session updated. That way field edits
# show up in the same chain history as AI turns, and can be undone by
# jumping back to an earlier run.

from pydantic import BaseModel


class FieldEditBody(BaseModel):
    value: str


@runs_router.patch("/{run_id}/fields/{field_id}")
def edit_run_field(
    run_id: int,
    field_id: str,
    body: FieldEditBody,
    ctx: OrgContext = Depends(require_org),
    db: DbSession = Depends(get_db),
):
    parent = db.get(AgentRun, run_id)
    if parent is None or parent.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Run not found")
    if not ctx.is_org_admin and parent.user_id != ctx.user.id:
        raise HTTPException(status_code=403, detail="Not your run")

    agent = db.get(Agent, parent.agent_id)
    if agent is None or agent.type != "rca_investigation":
        raise HTTPException(status_code=400, detail="Field edits only supported for Investigation")

    from app.agents.rca_investigation.session_state import (
        FieldEdit as SessionFieldEdit,
        Message,
        MessageRole,
        Session as RcaSession,
    )
    from app.agents.rca_investigation.template import FieldStatus

    session_dict = (parent.output or {}).get("session")
    if not session_dict:
        raise HTTPException(status_code=400, detail="Run has no session to edit")

    session = RcaSession.model_validate(session_dict)
    if field_id not in session.fields:
        raise HTTPException(status_code=400, detail=f"Unknown field: {field_id}")

    old_value = session.fields[field_id].value
    new_value = body.value or ""
    session.fields[field_id].value = new_value
    session.fields[field_id].status = FieldStatus.FILLED if new_value.strip() else FieldStatus.EMPTY
    session.fields[field_id].last_edited_by = "user"
    session.field_edit_history.append(SessionFieldEdit(
        field_id=field_id,
        old_value=old_value[:200],
        new_value=new_value[:200],
        edited_by="user",
    ))

    label = session.fields[field_id].label
    session.add_message(Message(
        role=MessageRole.USER,
        content=f"(edited {label})",
        fields_updated=[field_id],
    ))

    output = {
        "session": session.model_dump(mode="json"),
        "agent_reply": f"Updated {label}.",
        "coverage_pct": session.coverage_pct(),
        "phase": session.phase.value,
        "fields_updated": [field_id],
        "coverage": session.coverage_snapshot(),
    }

    new_run = AgentRun(
        org_id=ctx.org_id,
        agent_id=parent.agent_id,
        user_id=ctx.user.id,
        parent_run_id=parent.id,
        status="completed",
        input={"edit": {"field_id": field_id, "old": old_value, "new": new_value}},
        output=output,
        duration_ms=0,
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    db.add(AuditLog(
        org_id=ctx.org_id,
        user_id=ctx.user.id,
        action="agent.field_edit",
        target_type="agent_run",
        target_id=str(new_run.id),
        meta={"agent_type": agent.type, "field_id": field_id, "parent_run_id": parent.id},
    ))
    db.commit()

    return _run_out(new_run)


# ── GET /api/runs/{run_id}/export.docx ───────────────────────────────────────

@runs_router.get("/{run_id}/export.docx")
def export_run_docx(
    run_id: int,
    ctx: OrgContext = Depends(require_org),
    db: DbSession = Depends(get_db),
):
    run = db.get(AgentRun, run_id)
    if run is None or run.org_id != ctx.org_id:
        raise HTTPException(status_code=404, detail="Run not found")
    if not ctx.is_org_admin and run.user_id != ctx.user.id:
        raise HTTPException(status_code=403, detail="Not your run")

    agent = db.get(Agent, run.agent_id)
    if agent is None or agent.type != "rca_investigation":
        raise HTTPException(status_code=400, detail="DOCX export not supported for this agent")

    session_dict = (run.output or {}).get("session")
    if not session_dict:
        raise HTTPException(status_code=400, detail="Run has no session to export")

    from app.agents.rca_investigation import generate_docx
    from app.agents.rca_investigation.session_state import Session as RcaSession

    session = RcaSession.model_validate(session_dict)
    buffer = generate_docx(session)

    ref = session.fields.get("document_ref_number")
    ref_str = (ref.value.split("\n")[0][:50] if ref and ref.value else "") or f"run-{run.id}"
    # sanitize filename
    import re
    clean = re.sub(r"[^a-zA-Z0-9#\-_]", "_", ref_str)
    clean = re.sub(r"_+", "_", clean).strip("_") or f"run-{run.id}"
    filename = f"Investigation_Report_{clean}.docx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
