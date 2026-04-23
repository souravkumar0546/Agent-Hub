"""Session state for the Investigation agent — Pydantic, serializable to JSON.

A Session holds the template fields + message history + edit log for one
investigation. It is persisted in `AgentRun.output["session"]` so each turn
reloads the prior state.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field

from app.agents.rca_investigation.template import (
    FieldStatus,
    TemplateField,
    build_template_fields,
)


class MessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class Attachment(BaseModel):
    filename: str
    size: int = 0
    content_type: str = ""


class Message(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    fields_updated: list[str] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)


class FieldEdit(BaseModel):
    field_id: str
    old_value: str
    new_value: str
    edited_by: str
    edited_at: datetime = Field(default_factory=datetime.utcnow)


class Phase(str, Enum):
    INTAKE = "intake"
    GAP_ANALYSIS = "gap_analysis"
    TARGETED_QA = "targeted_qa"
    DRAFTING = "drafting"
    REVIEW = "review"
    COMPLETE = "complete"


class Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    phase: Phase = Phase.INTAKE

    owner_name: str = ""
    owner_employee_id: str = ""
    owner_department: str = ""

    fields: dict[str, TemplateField] = Field(default_factory=build_template_fields)
    messages: list[Message] = Field(default_factory=list)
    field_edit_history: list[FieldEdit] = Field(default_factory=list)

    def coverage_pct(self) -> float:
        countable = [
            f for f in self.fields.values()
            if f.priority.value in ("required", "conditional")
        ]
        if not countable:
            return 0.0
        filled = sum(
            1 for f in countable
            if f.status in (FieldStatus.FILLED, FieldStatus.NEEDS_REVIEW)
        )
        partial = sum(1 for f in countable if f.status == FieldStatus.PARTIAL)
        return round((filled + partial * 0.5) / len(countable) * 100, 1)

    def coverage_snapshot(self) -> dict[str, str]:
        return {fid: f.status.value for fid, f in self.fields.items()}

    def add_message(self, msg: Message):
        self.messages.append(msg)
        self.updated_at = datetime.utcnow()

    def record_field_edit(self, field_id: str, old_value: str, new_value: str, edited_by: str):
        self.field_edit_history.append(FieldEdit(
            field_id=field_id,
            old_value=old_value[:200],
            new_value=new_value[:200],
            edited_by=edited_by,
        ))
