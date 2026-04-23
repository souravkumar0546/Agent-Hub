"""Field classification, priority questions, and SOP rules.

Ported verbatim from Devio core/field_config.py.
"""

from __future__ import annotations


# Field classifications:
#   session  — auto-filled from login session
#   user     — only user can provide
#   analysis — agent MUST fill from whatever it has
#   hybrid   — extract from narrative if mentioned, ask if not
#   auto     — filled by deterministic code, no LLM
#   optional — LLM fills only if user explicitly requests

FIELD_CLASS: dict[str, str] = {
    "initiator": "session",

    "document_ref_number": "user",
    "investigation_team": "user",
    "gemba_walk": "user",

    "sequence_of_events": "hybrid",
    "immediate_actions": "hybrid",
    "reference_docs": "hybrid",
    "historical_similar_events": "hybrid",
    "historical_data_source": "hybrid",

    "description": "analysis",
    "source_type": "analysis",
    "source_category": "analysis",
    "preliminary_impact": "analysis",
    "five_why": "analysis",
    "root_causes": "analysis",
    "brainstorming": "analysis",
    "fishbone": "optional",
    "process_mapping": "analysis",
    "fault_tree": "optional",
    "pareto": "optional",
    "data_summary": "analysis",
    "impact_product_quality": "analysis",
    "impact_other_products": "analysis",
    "impact_other_batches": "analysis",
    "impact_qms_regulatory": "analysis",
    "impact_validated_state": "analysis",
    "impact_pm_calibration": "analysis",
    "corrections": "analysis",
    "corrective_actions": "analysis",
    "preventive_actions": "analysis",
    "conclusion": "analysis",
    "historical_root_cause_eval": "analysis",

    "historical_timeframe": "auto",
    "historical_justification": "auto",
    "abbreviations": "auto",
}


QUESTION_PRIORITY: list[dict] = [
    {
        "field_id": "immediate_actions",
        "question": "What immediate actions were taken to contain the issue?",
        "unlocks": ["corrections", "corrective_actions", "conclusion"],
    },
    {
        "field_id": "sequence_of_events",
        "question": "Can you walk me through the sequence of events — what happened step by step?",
        "unlocks": ["five_why", "root_causes", "process_mapping"],
    },
    {
        "field_id": "reference_docs",
        "question": "Which equipment, SOPs, or batch numbers are involved?",
        "unlocks": ["impact_product_quality", "impact_other_batches", "abbreviations"],
    },
    {
        "field_id": "document_ref_number",
        "question": "Do you have a PR number or document reference for this?",
        "unlocks": ["historical_root_cause_eval", "historical_similar_events"],
    },
    {
        "field_id": "investigation_team",
        "question": "Who is on the investigation team? (Name, Employee ID, Department)",
        "unlocks": [],
    },
    {
        "field_id": "historical_data_source",
        "question": "Which data sources were reviewed for historical check (logbooks, TrackWise, etc.)?",
        "unlocks": ["historical_root_cause_eval"],
    },
    {
        "field_id": "gemba_walk",
        "question": "Was a GEMBA walk conducted? If so, what were the findings?",
        "unlocks": [],
    },
    {
        "field_id": "historical_similar_events",
        "question": "Are there any similar past events or PR numbers from historical review?",
        "unlocks": ["historical_root_cause_eval"],
    },
]


FIELD_SOP_RULES: dict[str, str] = {
    "source_type": 'Must be exactly one of: "Deviation", "OOS", "OOT", "Customer Complaint".',
    "source_category": 'Must be exactly one of: "Critical", "Major", "Minor". IT/system/documentation = Minor, product impact = Major, patient safety = Critical.',
    "description": "Use What, Where, When, Who, Which, How structure per SOP 7.3.2. PRESERVE ALL details from user input — names, emp IDs, dates, counts, desired state, actual state, delay justification, attachment references. Do NOT summarize or condense. The description should be at least as detailed as the original input.",
    "preliminary_impact": "Initial assessment before full investigation. State what systems/products/processes are potentially affected.",
    "immediate_actions": "Actions taken to minimize impact. If not applicable, provide justification per SOP 7.4.1.",
    "historical_timeframe": "Minimum 12 months per SOP 7.4.3.1. Justify if shorter.",
    "five_why": "Build Why1 through Why5 chain. Each Why must follow logically from the previous answer.",
    "root_causes": "State as 'Definitive', 'Most Probable', or 'Contributing Factor'. Per SOP 7.5.11.",
    "corrections": "Immediate corrections already taken. Each action as: numbered item, action text, department, 'Completed' or date. Do NOT include column headers like 'Sl. No.' or 'Responsibility' — the report template adds those.",
    "corrective_actions": "Actions to eliminate root cause. Each action as: numbered item, action text, department, relative timeline (e.g. 'Within 15 working days from approval'). NEVER use specific calendar dates. Do NOT include column headers like 'Sl. No.' — the report template adds those.",
    "preventive_actions": "Actions to prevent recurrence. Each action as: numbered item, action text, department, relative timeline (e.g. 'Within 30 working days from approval'). NEVER use specific calendar dates. Do NOT include column headers like 'Sl. No.' — the report template adds those.",
    "conclusion": "Summarize: what happened, root cause, impact assessment, and CAPAs. Per SOP 7.8.",
    "impact_product_quality": "Assess impact on product quality. For IT/system deviations, explain why there is no product impact.",
    "impact_other_products": "Assess if other products in the same facility/lab could be affected.",
    "impact_other_batches": "Assess impact on other batches, equipment, facility, systems, documents.",
    "impact_qms_regulatory": "Assess impact on QMS, compliance, and regulatory submissions.",
    "impact_validated_state": "Assess impact on validated state of product/process/method/stability.",
    "impact_pm_calibration": "Assess impact on preventive maintenance, calibration, or qualification status.",
}


def get_priority_questions(empty_field_ids: set[str], max_questions: int = 3) -> list[dict]:
    questions = []
    for q in QUESTION_PRIORITY:
        if q["field_id"] in empty_field_ids:
            questions.append(q)
        if len(questions) >= max_questions:
            break
    return questions


def get_analysis_field_ids() -> list[str]:
    return [fid for fid, cls in FIELD_CLASS.items() if cls in ("analysis", "hybrid")]


def get_user_field_ids() -> list[str]:
    return [fid for fid, cls in FIELD_CLASS.items() if cls == "user"]


def get_askable_field_ids() -> list[str]:
    return [fid for fid, cls in FIELD_CLASS.items() if cls in ("user", "hybrid")]
