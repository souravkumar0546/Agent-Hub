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

from sqlalchemy.orm import Session

from app.agents.cacm.kpi_catalog import kpi_by_type
from app.agents.cacm.schedule_math import compute_next_run_at
from app.api.routes.cacm import _run_in_background  # noqa: E402
from app.models.cacm import CacmRun, CacmSchedule


log = logging.getLogger(__name__)


_TICK_INTERVAL_SECONDS = 60


def _process_label(kpi_type: str) -> str:
    """Mirror what POST /runs does — read the KPI catalog to get the
    process label that gets stored on CacmRun."""
    kpi = kpi_by_type(kpi_type)
    return kpi.process if kpi else "unknown"


def _kick_off(run_id: int) -> None:
    """Fire `_run_in_background(run_id)`. If we're inside a running asyncio
    loop (production path), schedule it as a task; otherwise (test path or
    sync entry), run it to completion via `asyncio.run`."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(_run_in_background(run_id))
        return
    loop.create_task(_run_in_background(run_id))


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

            _kick_off(run.id)

            sched.last_run_id = run.id
            sched.last_run_at = now
            sched.next_run_at = compute_next_run_at(
                sched.frequency, sched.time_of_day, now=now,
            )
            db.commit()
    finally:
        db.close()


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
