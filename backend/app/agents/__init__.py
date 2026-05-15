"""Agent catalog.

Each entry describes one agent type available on the platform. The seed script
creates a row in the `agents` table for each entry when an org is provisioned.
The `module` string points to the implementation package under `app/agents/` —
those are stubs for now and will be filled in per-agent.
"""

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True)
class AgentDef:
    type: str
    name: str
    tagline: str
    category: str
    icon: str
    # Short, brand-style product name shown as the card headline. Falls
    # back to `name` at the serializer boundary when absent, so legacy DB
    # rows without a CATALOG match still render. Keep it ≤ 12 chars.
    display_name: str = ""
    default_departments: tuple[str, ...] = field(default_factory=tuple)  # dept slugs
    module: str = ""
    # True once the agent's module has a working `run()` implementation.
    # Drives list ordering (implemented agents float to the top) and lets
    # the UI badge stubs as "coming soon".
    implemented: bool = False
    # Surface namespace: "agent" (default) shows in the Agents Hub / Library;
    # "application" splits into the parallel My Applications / Application
    # Library views. The classification is derived at serialization time
    # from CATALOG — no DB column / migration. New catalog entries default
    # to "agent" so the platform stays backwards-compatible.
    kind: Literal["agent", "application"] = "agent"


def is_implemented(agent_type: str) -> bool:
    for d in CATALOG:
        if d.type == agent_type:
            return d.implemented
    return False


def kind_for(agent_type: str) -> str:
    """Return "agent" or "application" for the given catalog type.

    Falls back to "agent" if the type isn't in CATALOG so legacy DB rows
    without a matching catalog entry default to the original namespace.
    """
    for d in CATALOG:
        if d.type == agent_type:
            return d.kind
    return "agent"


CATALOG: list[AgentDef] = [
    AgentDef(
        type="project_status",
        display_name="Pace",
        name="Project Status Agent",
        tagline="Tracks project milestones. Flags slips and dependencies as they happen, with owners.",
        category="PMO",
        icon="chart",
        default_departments=("pmo",),
        module="app.agents.project_status",
    ),
    AgentDef(
        type="meeting_mom",
        display_name="Scribe",
        name="Meeting & MoM Agent",
        tagline="Turns a meeting into a transcript, a decision log, and action items in about five minutes.",
        category="Productivity",
        icon="mic",
        default_departments=(),  # org-wide
        module="app.agents.meeting_mom",
    ),
    AgentDef(
        type="hr_service",
        display_name="Haven",
        name="HR Service Agent",
        tagline="Answers questions about leave, Form 16, comp, and policy. Pulls from your handbook, doesn't make things up.",
        category="HR",
        icon="users",
        default_departments=("hr",),
        module="app.agents.hr_service",
    ),
    AgentDef(
        type="hiring_visibility",
        display_name="Scout",
        name="Hiring Visibility Agent",
        tagline="Shows where every candidate is in your pipeline, how busy each interviewer is, and how long offers take.",
        category="Talent",
        icon="trending",
        default_departments=("talent",),
        module="app.agents.hiring_visibility",
    ),
    AgentDef(
        type="learning_journey",
        display_name="Mentor",
        name="Learning Journey Agent",
        tagline="Builds a learning plan for each person based on their role, the skills they're missing, and what they've read.",
        category="L&D",
        icon="book",
        default_departments=("learning",),
        module="app.agents.learning_journey",
    ),
    AgentDef(
        type="vendor_identification",
        display_name="Ledger",
        name="Vendor Identification Agent",
        tagline="Maps parent and child vendors. Spots where you're paying twice and suggests supplier matches.",
        category="Procurement",
        icon="box",
        default_departments=("procurement",),
        module="app.agents.vendor_identification",
    ),
    AgentDef(
        type="rnd_material_visibility",
        display_name="Atlas",
        name="R&D Material Visibility",
        tagline="Shows what materials R&D and clinical teams have on hand across sites, plus what to order next.",
        category="R&D",
        icon="flask",
        default_departments=("rnd", "procurement"),
        module="app.agents.rnd_material_visibility",
    ),
    AgentDef(
        type="commercial_chatbot",
        display_name="Pitch",
        name="Commercial Insights Agent",
        tagline="Answers sales questions in seconds. Finds the right slide, the right case study, the right reference.",
        category="Commercial",
        icon="chat",
        default_departments=("commercial",),
        module="app.agents.commercial_chatbot",
    ),
    AgentDef(
        type="molecule_pipeline",
        display_name="Lens",
        name="Molecule Pipeline Intelligence",
        tagline="Watches for new molecules, competitor moves, and market signals. Always shows where it found them.",
        category="Commercial",
        icon="pipeline",
        default_departments=("commercial_intel", "commercial"),
        module="app.agents.molecule_pipeline",
    ),
    AgentDef(
        type="fda_483_compliance",
        display_name="Aegis",
        name="483 FDA Compliance Agent",
        tagline="Drafts a response to an FDA 483 with the precedents you'd want to cite. Faster than starting from scratch.",
        category="Compliance",
        icon="shield",
        default_departments=("qa_compliance",),
        module="app.agents.fda_483_compliance",
    ),
    AgentDef(
        type="rca_investigation",
        # "Devio" — carries the heritage name of the module this was ported
        # from; fits the investigate/detect register alongside Forge / Atlas.
        display_name="Devio",
        name="RCA / Investigation Agent",
        tagline="Enables faster and more accurate deviation investigation reports — reducing turnaround time by 60% and delivering reliable RCA and impact analysis through an interactive chatbot.",
        category="Compliance",
        icon="search",
        default_departments=("qa_compliance", "rnd"),
        module="app.agents.rca_investigation",
        implemented=True,
    ),

    # ── DMAhub agents — ported from the DMAhub project. Pipeline-style
    # (upload Excel → map columns → AI assist → export). Implemented + live.
    AgentDef(
        type="data_classifier",
        display_name="Curator",
        name="Data Classifier",
        tagline="Streamlines data classification by organizing thousands of records into a taxonomy defined by the user, reducing manual effort by 70% with built-in review and override.",
        category="Data Management",
        icon="box",
        default_departments=(),
        module="app.dma",
        implemented=True,
    ),
    AgentDef(
        type="master_builder",
        display_name="Forge",
        name="Master Builder",
        tagline="Enables creation of a governed master dataset by consolidating classifications, with full traceability and seamless inline review.",
        category="Data Management",
        icon="flask",
        default_departments=(),
        module="app.dma",
        implemented=True,
    ),
    AgentDef(
        type="data_enrichment",
        display_name="Echo",
        name="Data Enrichment",
        tagline="Enriches your data by adding missing attributes from external sources, while preserving original values for full traceability.",
        category="Data Management",
        icon="book",
        default_departments=(),
        module="app.dma",
        implemented=True,
    ),
    AgentDef(
        type="group_duplicates",
        display_name="Twin",
        name="Group Duplicates",
        tagline="Uncovers hidden and indirect duplicates in material master data, enabling golden record creation, strengthening GxP compliance and audit readiness, and reducing duplicates by 60–70% while improving procurement and inventory efficiency.",
        category="Data Management",
        icon="users",
        default_departments=(),
        module="app.dma",
        implemented=True,
    ),
    AgentDef(
        type="lookup_agent",
        # "Sonar" — detect/locate-a-match vibe, short and distinct from the
        # classifier's `group_match_confirmed` method label.
        display_name="Sonar",
        name="Lookup Agent",
        tagline="Evaluates how closely records match across columns, generating a unified weighted score to support precise decision-making.",
        category="Data Management",
        icon="search",
        default_departments=(),
        module="app.dma",
        implemented=True,
    ),

    # ── CACM — Continuous Audit & Continuous Monitoring. Walks SAP-style
    # KPIs/KRIs through a 6-stage pipeline (extract → transform → load →
    # rules → exceptions → dashboard). Lives under /api/cacm/*.
    AgentDef(
        type="cacm",
        display_name="Prism",
        name="Prism",
        tagline="A technology-enabled audit and risk monitoring solution designed to identify control gaps.",
        category="Control Effectiveness Monitoring",
        icon="shield-check",
        default_departments=("qa_compliance",),
        module="app.agents.cacm",
        implemented=True,
        # Prism is the first entry in the new "Applications" namespace —
        # surfaces in My Applications / Application Library rather than
        # the Agents Hub. URL stays /agents/cacm; only the classification
        # changes.
        kind="application",
    ),
]


def display_name_for(agent_type: str) -> str:
    """Look up the short brand-style name (e.g. "Vera" for RCA).

    Returns empty string when no CATALOG match — serializer callers treat
    that as "fall back to the stored `Agent.name`" so legacy DB rows with
    no matching catalog entry still render a sensible title.
    """
    for d in CATALOG:
        if d.type == agent_type:
            return d.display_name or ""
    return ""
