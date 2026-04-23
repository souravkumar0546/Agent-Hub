"""Investigation agent orchestrator — two-phase pipeline.

Ported from Devio core/agent.py. Adapted to use the shared `AIEngine` (instead
of Devio's per-session provider) and the agent's own `session_state` types.

Phase 1 — single LLM tool call extracting all fields + intent + affected + cleared.
Phase 2 — parallel LLM calls rewriting raw facts into formal GMP prose.
Pre/post-processing is deterministic code.
"""

from __future__ import annotations

import asyncio
import re
from datetime import datetime

from app.core.ai_engine import AIEngine
from app.agents.rca_investigation.field_config import (
    FIELD_CLASS,
    FIELD_SOP_RULES,
    get_analysis_field_ids,
    get_askable_field_ids,
    get_priority_questions,
    get_user_field_ids,
)
from app.agents.rca_investigation.prompts import (
    PHASE1_SYSTEM,
    PHASE1_USER_CONTEXT,
    PHASE2_SYSTEM,
)
from app.agents.rca_investigation.session_state import (
    Message,
    MessageRole,
    Phase,
    Session,
)
from app.agents.rca_investigation.sop_rules import validate_sop_compliance
from app.agents.rca_investigation.style import get_style_examples_for_section
from app.agents.rca_investigation.template import FieldStatus


VALID_FIELD_IDS = [
    "source_type", "source_category", "document_ref_number",
    "description", "reference_docs", "initiator",
    "preliminary_impact", "immediate_actions",
    "historical_data_source", "historical_timeframe", "historical_justification", "historical_similar_events",
    "investigation_team", "sequence_of_events",
    "gemba_walk", "process_mapping", "brainstorming", "fishbone", "fault_tree", "pareto", "five_why",
    "data_summary", "historical_root_cause_eval", "root_causes",
    "impact_product_quality", "impact_other_products", "impact_other_batches",
    "impact_qms_regulatory", "impact_validated_state", "impact_pm_calibration",
    "corrections", "corrective_actions", "preventive_actions",
    "conclusion", "abbreviations",
]


PHASE1_TOOL_SCHEMA = {
    "type": "object",
    "properties": {
        "intent": {
            "type": "string",
            "enum": ["new_info", "correction", "question", "command"],
        },
        "extractions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_id": {"type": "string", "enum": VALID_FIELD_IDS},
                    "value": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["field_id", "value", "confidence"],
            },
        },
        "affected_fields": {
            "type": "array",
            "items": {"type": "string", "enum": VALID_FIELD_IDS},
        },
        "clear_fields": {
            "type": "array",
            "items": {"type": "string", "enum": VALID_FIELD_IDS},
        },
    },
    "required": ["intent", "extractions", "affected_fields"],
}


# ── Short-field sanitizers ────────────────────────────────────────────────────

def _match_source_type(value: str) -> str:
    v = value.strip().lower()
    for opt in ["Deviation", "OOS", "OOT", "Customer Complaint"]:
        if v == opt.lower():
            return opt
    if re.search(r"\bdeviation\b", v):
        return "Deviation"
    if re.search(r"\bcustomer\s+complaint\b", v):
        return "Customer Complaint"
    if re.search(r"\boos\b", v) or "out of specification" in v:
        return "OOS"
    if (re.search(r"\boot\b", v) or "out of trend" in v) and "troublesh" not in v:
        return "OOT"
    return "Deviation"


def _match_category(value: str) -> str:
    v = value.strip().lower()
    if v in ("critical", "major", "minor"):
        return v.capitalize()
    if re.search(r"\bcritical\b", v):
        return "Critical"
    if re.search(r"\bmajor\b", v):
        return "Major"
    return "Minor"


def _strip_markdown(text: str) -> str:
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    text = re.sub(r"^[-*]\s+", "", text, flags=re.MULTILINE)
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`(.+?)`", r"\1", text)
    text = re.sub(r"^\d+\.\d*\s+[A-Z][^:]+:\s*\n", "", text, flags=re.MULTILINE)
    return text.strip()


SHORT_FIELD_RULES = {
    "source_type": _match_source_type,
    "source_category": _match_category,
    "document_ref_number": lambda v: v.split("\n")[0][:100].strip(),
    "initiator": lambda v: v.split("\n")[0][:200].strip(),
}


def _sanitize_field(field_id: str, value: str) -> str:
    rule = SHORT_FIELD_RULES.get(field_id)
    return rule(value) if rule else _strip_markdown(value)


# ── Pre-processing ────────────────────────────────────────────────────────────

def _auto_fill_session_fields(session: Session) -> None:
    if session.owner_name and not session.fields["initiator"].value:
        parts = [session.owner_name]
        if session.owner_employee_id:
            parts.append(f"Employee ID: {session.owner_employee_id}")
        if session.owner_department:
            parts.append(session.owner_department)
        session.fields["initiator"].value = ", ".join(parts)
        session.fields["initiator"].status = FieldStatus.FILLED
        session.fields["initiator"].last_edited_by = "auto"

    if not session.fields["historical_timeframe"].value:
        session.fields["historical_timeframe"].value = "12 months"
        session.fields["historical_timeframe"].status = FieldStatus.FILLED
        session.fields["historical_timeframe"].last_edited_by = "auto"


def _build_phase1_system(session: Session) -> str:
    analysis_list = ", ".join(get_analysis_field_ids())
    user_list = ", ".join(get_user_field_ids())
    filled_lines = [
        f"  {fid}: {f.value[:120]}..." for fid, f in session.fields.items() if f.value
    ]
    filled_summary = "\n".join(filled_lines) if filled_lines else "  (none — this is the first message)"
    return PHASE1_SYSTEM.format(
        analysis_fields_list=analysis_list,
        user_fields_list=user_list,
        filled_fields_summary=filled_summary,
    )


def _build_phase1_user_context(session: Session, user_text: str) -> str:
    recent = []
    for msg in session.messages[-6:]:
        if msg.role == MessageRole.SYSTEM:
            continue
        role = "User" if msg.role == MessageRole.USER else "Agent"
        recent.append(f"{role}: {msg.content[:300]}")
    recent_text = "\n".join(recent) if recent else "(first message in conversation)"

    initiator = ""
    if session.owner_name:
        parts = [session.owner_name]
        if session.owner_employee_id:
            parts.append(f"Employee ID: {session.owner_employee_id}")
        if session.owner_department:
            parts.append(session.owner_department)
        initiator = ", ".join(parts)

    return PHASE1_USER_CONTEXT.format(
        user_message=user_text,
        recent_messages=recent_text,
        initiator_info=initiator or "Not provided",
    )


# ── Smart merge logic ─────────────────────────────────────────────────────────

def _compute_fields_to_write(
    session: Session,
    extractions: list[dict],
    affected_fields: list[str],
    intent: str,
) -> list[dict]:
    to_write: list[dict] = []
    seen: set[str] = set()

    for ext in extractions:
        fid = ext.get("field_id")
        value = ext.get("value", "")
        if not fid or fid not in session.fields or not value.strip():
            continue
        field_obj = session.fields[fid]
        if field_obj.last_edited_by == "user" and intent != "correction":
            continue
        if FIELD_CLASS.get(fid) in ("auto", "session"):
            continue
        to_write.append(ext)
        seen.add(fid)

    for fid in affected_fields:
        if fid in seen or fid not in session.fields:
            continue
        field_obj = session.fields[fid]
        if field_obj.last_edited_by == "user":
            continue
        if field_obj.value:
            to_write.append({"field_id": fid, "value": field_obj.value, "confidence": 0.7})
            seen.add(fid)

    return to_write


# ── Phase 2: parallel GMP writing ─────────────────────────────────────────────

async def _write_field_gmp(engine: AIEngine, field_id: str, raw_value: str, session: Session) -> tuple[str, str]:
    field_obj = session.fields[field_id]

    if field_id in SHORT_FIELD_RULES:
        return field_id, _sanitize_field(field_id, raw_value)

    style_ex = get_style_examples_for_section(field_id, max_chars=1500)
    if not style_ex or len(style_ex) < 30:
        style_ex = "(No style example available for this section. Write formal GMP prose.)"

    sop_rule = FIELD_SOP_RULES.get(field_id, "Write in formal GMP language suitable for regulatory review.")
    prompt = PHASE2_SYSTEM.format(
        field_label=field_obj.label,
        field_section=field_obj.section,
        sop_rule=sop_rule,
        raw_facts=raw_value,
        style_example=style_ex,
    )

    try:
        gmp_text = await engine.complete(prompt, "Write this section now.", max_tokens=1000)
        return field_id, _strip_markdown(gmp_text)
    except Exception as e:
        print(f"[PHASE2] Failed to write {field_id}: {e}")
        return field_id, _strip_markdown(raw_value)


# ── Abbreviations auto-fill ──────────────────────────────────────────────────

KNOWN_ABBREVIATIONS: dict[str, str] = {
    "GMP": "Good Manufacturing Practice", "SOP": "Standard Operating Procedure",
    "QA": "Quality Assurance", "QC": "Quality Control", "QMS": "Quality Management System",
    "CAPA": "Corrective and Preventive Action", "OOS": "Out of Specification",
    "OOT": "Out of Trend", "PR": "Problem Report", "LMS": "Learning Management System",
    "CIP": "Clean in Place", "SIP": "Sterilize in Place", "WFI": "Water for Injection",
    "PW": "Purified Water", "API": "Active Pharmaceutical Ingredient", "FP": "Finished Product",
    "RM": "Raw Material", "PM": "Preventive Maintenance", "IQ": "Installation Qualification",
    "OQ": "Operational Qualification", "PQ": "Performance Qualification", "DQ": "Design Qualification",
    "FAT": "Factory Acceptance Test", "SAT": "Site Acceptance Test",
    "URS": "User Requirement Specification", "FRS": "Functional Requirement Specification",
    "CSV": "Computer System Validation", "SAP": "Systems, Applications and Products",
    "HR": "Human Resources", "IT": "Information Technology", "SSO": "Single Sign-On",
    "RCA": "Root Cause Analysis", "EHS": "Environment, Health and Safety",
    "BMR": "Batch Manufacturing Record", "BPR": "Batch Packaging Record",
    "SDS": "Safety Data Sheet", "MSDS": "Material Safety Data Sheet",
    "PPE": "Personal Protective Equipment", "GDP": "Good Documentation Practice",
    "GLP": "Good Laboratory Practice", "ICH": "International Council for Harmonisation",
    "FDA": "Food and Drug Administration", "WHO": "World Health Organization",
    "HVAC": "Heating, Ventilation and Air Conditioning", "AHU": "Air Handling Unit",
    "LAF": "Laminar Air Flow", "HEPA": "High Efficiency Particulate Air",
    "EDMS": "Electronic Document Management System", "ERP": "Enterprise Resource Planning",
    "LIMS": "Laboratory Information Management System", "MFR": "Master Formula Record",
    "BOM": "Bill of Materials", "COA": "Certificate of Analysis", "MOC": "Management of Change",
    "FMEA": "Failure Mode and Effects Analysis", "FTA": "Fault Tree Analysis",
    "NA": "Not Applicable", "ID": "Identification", "Emp": "Employee", "HOD": "Head of Department",
}


def _extract_abbreviations(session: Session) -> tuple[list[str], list[str]]:
    abbrevs: set[str] = set()
    for f in session.fields.values():
        if f.value:
            abbrevs.update(re.findall(r"\b[A-Z]{2,6}\b", f.value))
    skip = {
        "THE", "AND", "FOR", "BUT", "NOT", "ALL", "ARE", "WAS", "HAS", "HAD",
        "WILL", "CAN", "MAY", "MUST", "FROM", "WITH", "THIS", "THAT", "BEEN",
        "NO", "OR", "IF", "SO", "AS", "BY", "TO", "IN", "ON", "AT", "OF",
        "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII",
        "AN", "IS", "DO", "UP", "HE", "WE", "AM", "BE", "GO",
    }
    abbrevs -= skip

    lines: list[str] = []
    unknown: list[str] = []
    for abbr in sorted(abbrevs):
        full = KNOWN_ABBREVIATIONS.get(abbr, "")
        if full:
            lines.append(f"{abbr} - {full}")
        else:
            unknown.append(abbr)
    return lines, unknown


async def _fill_abbreviations(session: Session, engine: AIEngine) -> None:
    known_lines, unknown = _extract_abbreviations(session)
    if unknown:
        try:
            prompt = (
                "Expand these abbreviations used in a GMP pharmaceutical investigation report. "
                "Return ONLY the expansions in the format 'ABBR - Full Form', one per line. "
                "If you cannot determine the expansion, skip it.\n\n" + ", ".join(unknown)
            )
            result = await engine.complete(prompt, "Expand now.", max_tokens=500)
            for line in result.strip().split("\n"):
                line = line.strip()
                if " - " in line and line.split(" - ")[0].strip().isupper():
                    known_lines.append(line)
        except Exception as e:
            print(f"[ABBREV] LLM expansion failed: {e}")
            for abbr in unknown:
                known_lines.append(abbr)

    if not known_lines:
        return
    known_lines.sort()
    session.fields["abbreviations"].value = "\n".join(known_lines)
    session.fields["abbreviations"].status = FieldStatus.FILLED
    session.fields["abbreviations"].last_edited_by = "auto"


# ── Chat response builder (deterministic) ────────────────────────────────────

def _build_chat_response(
    fields_written: list[str],
    fields_rewritten: list[str],
    low_confidence_fields: list[tuple[str, float]],
    priority_questions: list[dict],
    intent: str,
    session: Session,
    fields_cleared: list[str] | None = None,
) -> str:
    if intent == "question":
        return ""

    parts: list[str] = []
    new_count = len(fields_written)
    updated_count = len(fields_rewritten)
    cleared_count = len(fields_cleared or [])

    action_parts = []
    if new_count:
        action_parts.append(f"filled {new_count} sections")
    if updated_count:
        action_parts.append(f"updated {updated_count} sections")
    if cleared_count:
        cleared_names = [session.fields[fid].label for fid in (fields_cleared or []) if fid in session.fields]
        action_parts.append(f"cleared {', '.join(cleared_names)}")
    if action_parts:
        parts.append("I've " + " and ".join(action_parts) + ".")

    if low_confidence_fields:
        names = [session.fields[fid].label for fid, _ in low_confidence_fields[:3]]
        parts.append(f"Please review: {', '.join(names)} — these were inferred with limited information.")

    if priority_questions:
        q_texts = [q["question"] for q in priority_questions]
        parts.append("To strengthen the report: " + " ".join(q_texts))

    return " ".join(parts)


def _update_phase(session: Session) -> None:
    c = session.coverage_pct()
    if c < 15:
        session.phase = Phase.INTAKE
    elif c < 40:
        session.phase = Phase.GAP_ANALYSIS
    elif c < 70:
        session.phase = Phase.TARGETED_QA
    elif c < 90:
        session.phase = Phase.DRAFTING
    else:
        session.phase = Phase.REVIEW


# ── Entry point ──────────────────────────────────────────────────────────────

async def process_user_message(
    session: Session,
    engine: AIEngine,
    user_text: str,
    attachments: list | None = None,
) -> str:
    """Process a single user turn. Mutates `session` in place."""

    user_msg = Message(role=MessageRole.USER, content=user_text, attachments=attachments or [])
    session.add_message(user_msg)

    _auto_fill_session_fields(session)

    # PHASE 1 ───────────────────────────────────────────────────────────────
    phase1_system = _build_phase1_system(session)
    phase1_context = _build_phase1_user_context(session, user_text)

    try:
        result = await engine.extract(
            phase1_system,
            phase1_context,
            tool_name="analyze_extraction",
            tool_description="Analyze the user message and extract all possible fields.",
            tool_schema=PHASE1_TOOL_SCHEMA,
            max_tokens=4000,
        )
    except Exception as e:
        print(f"[PHASE1] FAILED: {e}")
        agent_text = "I encountered an error analyzing your message. Please try again."
        session.add_message(Message(role=MessageRole.AGENT, content=agent_text))
        return agent_text

    intent = result.get("intent", "new_info")
    extractions = result.get("extractions", [])
    affected_fields = result.get("affected_fields", [])
    clear_fields = result.get("clear_fields", [])
    print(f"[PHASE1] intent={intent} extracted={len(extractions)} affected={affected_fields} clear={clear_fields}")

    # QUESTION intent: answer, don't touch fields ──────────────────────────
    if intent == "question":
        field_summary = [f"{f.label}: {f.value[:200]}" for fid, f in session.fields.items() if f.value]
        context = "\n".join(field_summary[:20])
        try:
            prompt = (
                "You are Devio, a GMP investigation assistant at Syngene. "
                f"The user asked: '{user_text}'\n\n"
                f"Answer based on the current investigation report:\n{context}\n\n"
                "Answer concisely in 2-3 sentences using specific details from the report. "
                "Do NOT make up information not in the report."
            )
            agent_text = _strip_markdown(await engine.complete(prompt, "Answer now.", max_tokens=400))
        except Exception:
            agent_text = "I can help with that. Could you clarify what you'd like me to do?"
        session.add_message(Message(role=MessageRole.AGENT, content=agent_text))
        return agent_text

    # CLEAR FIELDS ─────────────────────────────────────────────────────────
    fields_cleared: list[str] = []
    for fid in clear_fields:
        if fid in session.fields and session.fields[fid].value:
            old = session.fields[fid].value
            session.fields[fid].value = ""
            session.fields[fid].status = FieldStatus.EMPTY
            session.fields[fid].last_edited_by = "agent"
            session.record_field_edit(fid, old, "", "agent")
            fields_cleared.append(fid)

    # SMART MERGE ──────────────────────────────────────────────────────────
    to_write = _compute_fields_to_write(session, extractions, affected_fields, intent)
    existing_filled = {fid for fid, f in session.fields.items() if f.value}
    fields_written: list[str] = []
    fields_rewritten: list[str] = []
    low_confidence: list[tuple[str, float]] = []

    # PHASE 2: parallel writes ────────────────────────────────────────────
    if to_write:
        tasks = [_write_field_gmp(engine, ext["field_id"], ext["value"], session) for ext in to_write]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, res in enumerate(results):
            if isinstance(res, Exception):
                print(f"[PHASE2] task {i} failed: {res}")
                continue
            fid, gmp_text = res
            if not gmp_text.strip():
                continue
            old_value = session.fields[fid].value
            session.fields[fid].value = gmp_text
            session.fields[fid].status = FieldStatus.FILLED
            session.fields[fid].last_edited_by = "agent"
            session.fields[fid].last_edited_at = datetime.utcnow().isoformat()
            session.fields[fid].source_message_ids.append(user_msg.id)
            session.record_field_edit(fid, old_value, gmp_text, "agent")
            if fid in existing_filled:
                fields_rewritten.append(fid)
            else:
                fields_written.append(fid)
            conf = to_write[i].get("confidence", 0.8)
            if conf < 0.6:
                low_confidence.append((fid, conf))

    # POST-PROCESSING ─────────────────────────────────────────────────────
    await _fill_abbreviations(session, engine)
    warnings = validate_sop_compliance(session)

    empty_user_fields = {fid for fid in get_askable_field_ids() if not session.fields[fid].value}
    priority_questions = get_priority_questions(empty_user_fields)

    agent_text = _build_chat_response(
        fields_written=fields_written,
        fields_rewritten=fields_rewritten,
        low_confidence_fields=low_confidence,
        priority_questions=priority_questions,
        intent=intent,
        session=session,
        fields_cleared=fields_cleared,
    )
    if warnings:
        agent_text += "\n\n" + "\n".join(f"SOP Note: {w}" for w in warnings)

    _update_phase(session)

    session.add_message(Message(
        role=MessageRole.AGENT,
        content=agent_text,
        fields_updated=fields_written + fields_rewritten + fields_cleared,
    ))
    return agent_text
