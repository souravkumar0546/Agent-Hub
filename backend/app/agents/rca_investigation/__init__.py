"""RCA / Investigation agent — public entry point.

Exposes:
  async run(user, owner_dept_name, input_dict, prior_session_dict) -> output_dict
  generate_docx(session)                — re-exported for the DOCX export route

`input_dict` shape (from POST /api/agents/{id}/run):
  {
    "message": str,
    "attachments_text": str,   # extracted text from uploaded files
    "attachments_meta": [{"filename": str, "size": int, "content_type": str}, ...],
  }

`prior_session_dict` — the `session` dict from a parent run's output (or None for a fresh run).

`output_dict` shape:
  {
    "session": <serialized Session>,       # full state for next-turn load
    "agent_reply": str,
    "coverage_pct": float,
    "phase": str,
    "fields_updated": [field_id, ...],
    "coverage": {field_id: status, ...},
  }
"""

from __future__ import annotations

from typing import Any

from app.core.ai_engine import get_ai_engine
from app.agents.rca_investigation.engine import process_user_message
from app.agents.rca_investigation.report import generate_docx
from app.agents.rca_investigation.session_state import Attachment, Session


def _build_full_message(message: str, attachments_text: str) -> str:
    if not attachments_text:
        return message.strip()
    return (message.strip() + "\n\n--- ATTACHED DOCUMENTS ---\n\n" + attachments_text).strip()


async def run(
    *,
    owner_name: str,
    owner_employee_id: str,
    owner_department: str,
    input_dict: dict[str, Any],
    prior_session_dict: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one turn of the Investigation agent."""

    if prior_session_dict:
        session = Session.model_validate(prior_session_dict)
    else:
        session = Session()

    # Session-owner info (auto-fills `initiator` field on first turn)
    if owner_name:
        session.owner_name = owner_name
    if owner_employee_id:
        session.owner_employee_id = owner_employee_id
    if owner_department:
        session.owner_department = owner_department

    message = (input_dict or {}).get("message", "").strip()
    attachments_text = (input_dict or {}).get("attachments_text", "")
    attachments_meta_raw = (input_dict or {}).get("attachments_meta", [])
    attachments = [Attachment.model_validate(a) for a in attachments_meta_raw]

    full_message = _build_full_message(message, attachments_text)
    if not full_message:
        raise ValueError("message or attachments_text required")

    engine = get_ai_engine()
    agent_reply = await process_user_message(session, engine, full_message, attachments=attachments)

    last_msg = session.messages[-1]

    return {
        "session": session.model_dump(mode="json"),
        "agent_reply": agent_reply,
        "coverage_pct": session.coverage_pct(),
        "phase": session.phase.value,
        "fields_updated": last_msg.fields_updated,
        "coverage": session.coverage_snapshot(),
    }


__all__ = ["run", "generate_docx"]
