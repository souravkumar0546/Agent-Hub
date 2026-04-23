"""Template field definitions matching FORM-GMP-QA-0504.

Ported from Devio models/template.py. 35 fields across 8 sections.
"""

from __future__ import annotations

from enum import Enum
from pydantic import BaseModel, Field


class FieldStatus(str, Enum):
    EMPTY = "empty"
    PARTIAL = "partial"
    FILLED = "filled"
    NEEDS_REVIEW = "needs_review"


class FieldPriority(str, Enum):
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    OPTIONAL = "optional"


class TemplateField(BaseModel):
    field_id: str
    section: str
    label: str
    description: str = ""
    priority: FieldPriority = FieldPriority.REQUIRED
    status: FieldStatus = FieldStatus.EMPTY
    value: str = ""
    confidence: float = 0.0
    source_message_ids: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    last_edited_by: str = ""
    last_edited_at: str = ""


def build_template_fields() -> dict[str, TemplateField]:
    fields = [
        TemplateField(field_id="source_type", section="1", label="Source of Non-Conformity",
                      description="Deviation, OOS, OOT, Customer Complaint, or Other"),
        TemplateField(field_id="source_category", section="1", label="Category of Non-Conformity",
                      description="Critical, Major, or Minor"),
        TemplateField(field_id="document_ref_number", section="1", label="Document Reference Number",
                      description="PR number or reference ID for the non-conformity"),

        TemplateField(field_id="description", section="2.1", label="Description of Non-Conformity",
                      description="Clear, concise description with What, Where, When, Who, Which, How"),
        TemplateField(field_id="reference_docs", section="2.2",
                      label="Reference Documents/Instruments/Equipment/Products",
                      description="Equipment IDs, SOP references, batch numbers, instrument IDs"),
        TemplateField(field_id="initiator", section="2.3", label="Initiator Name and Department",
                      description="Person who identified the non-conformity and their department"),

        TemplateField(field_id="preliminary_impact", section="3.1",
                      label="Initial/Preliminary Impact Assessment",
                      description="Immediate assessment of impact on product, process, equipment"),
        TemplateField(field_id="immediate_actions", section="3.2",
                      label="Immediate Actions or Correction",
                      description="Actions taken to minimize impact. Justify if not applicable."),

        TemplateField(field_id="historical_data_source", section="4",
                      label="Reference of Relevant Data Source Reviewed",
                      description="Logbooks, TrackWise records, investigation reports, audit reports, etc."),
        TemplateField(field_id="historical_timeframe", section="4", label="Time Frame of Review",
                      description="Minimum 12 months. Justify if less."),
        TemplateField(field_id="historical_justification", section="4",
                      label="Justification for Review Period",
                      description="Required only if less than 12 months",
                      priority=FieldPriority.CONDITIONAL),
        TemplateField(field_id="historical_similar_events", section="4",
                      label="Similar Events (Earlier PR Numbers)",
                      description="Past PR references if historical checks found similar non-conformities"),

        TemplateField(field_id="investigation_team", section="5.1", label="Investigation Team",
                      description="Name, Employee ID, Designation, Department of team members",
                      priority=FieldPriority.CONDITIONAL),
        TemplateField(field_id="sequence_of_events", section="5.2", label="Sequence of Events",
                      description="Chronological timeline with date, time, and event details",
                      priority=FieldPriority.CONDITIONAL),

        TemplateField(field_id="gemba_walk", section="5.3.1", label="GEMBA Walk",
                      description="Date/time, location, personnel, findings, inference",
                      priority=FieldPriority.OPTIONAL),
        TemplateField(field_id="process_mapping", section="5.3.2",
                      label="Process Mapping and Gap Analysis",
                      description="What should happen vs what happened",
                      priority=FieldPriority.OPTIONAL),
        TemplateField(field_id="brainstorming", section="5.3.3", label="Brainstorming",
                      description="Date/time, personnel, problem statement, factors, inference",
                      priority=FieldPriority.OPTIONAL),
        TemplateField(field_id="fishbone", section="5.3.4", label="Fishbone Analysis (6M)",
                      description="Man, Machine, Material, Measurement, Method, Mother Nature + inference",
                      priority=FieldPriority.OPTIONAL),
        TemplateField(field_id="fault_tree", section="5.3.5", label="Fault Tree Analysis",
                      description="FTA diagram with AND/OR gates",
                      priority=FieldPriority.OPTIONAL),
        TemplateField(field_id="pareto", section="5.3.6", label="Pareto Analysis",
                      description="Frequency-based prioritization of causes",
                      priority=FieldPriority.OPTIONAL),
        TemplateField(field_id="five_why", section="5.3.7", label="5-Why Analysis",
                      description="Problem statement, Why1 through Why5, inference",
                      priority=FieldPriority.OPTIONAL),

        TemplateField(field_id="data_summary", section="5.4",
                      label="Summary of Data and Documents Reviewed",
                      description="Documents, data, experiments reviewed during investigation"),
        TemplateField(field_id="historical_root_cause_eval", section="5.5",
                      label="Evaluation of Root Cause with Historical Findings",
                      description="Compare current root cause with historical. PR Number, Root cause, CAPA table.",
                      priority=FieldPriority.CONDITIONAL),
        TemplateField(field_id="root_causes", section="5.6",
                      label="List of Root Causes and Contributing Factors",
                      description="Type (Definitive/Most Probable/Contributing factor) + Cause description"),

        TemplateField(field_id="impact_product_quality", section="6.1",
                      label="Impact on Quality of the Product"),
        TemplateField(field_id="impact_other_products", section="6.2",
                      label="Impact on Other Products in Same Facility/Lab"),
        TemplateField(field_id="impact_other_batches", section="6.3",
                      label="Impact on Other Batches, Equipment, Facility, Systems, Documents"),
        TemplateField(field_id="impact_qms_regulatory", section="6.4",
                      label="Impact on QMS, Compliance, and Regulatory Submissions"),
        TemplateField(field_id="impact_validated_state", section="6.5",
                      label="Impact on Validated State of Product/Process/Method/Stability"),
        TemplateField(field_id="impact_pm_calibration", section="6.6",
                      label="Impact on PM, Calibration, or Qualification Status"),

        TemplateField(field_id="corrections", section="7", label="Corrections",
                      description="Immediate corrections with responsibility and timeline"),
        TemplateField(field_id="corrective_actions", section="7", label="Corrective Actions",
                      description="Actions to eliminate root cause, with responsibility and target timeline"),
        TemplateField(field_id="preventive_actions", section="7", label="Preventive Actions",
                      description="Actions to prevent recurrence, with responsibility and target timeline"),

        TemplateField(field_id="conclusion", section="8", label="Conclusion",
                      description="Summary of non-conformity, investigation, RCA, impact, and CAPAs"),

        TemplateField(field_id="abbreviations", section="10", label="Abbreviations",
                      description="List of abbreviations used in the report",
                      priority=FieldPriority.OPTIONAL),
    ]
    return {f.field_id: f for f in fields}
