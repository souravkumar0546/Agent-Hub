"""Agent catalog.

Each entry describes one agent type available on the platform. The seed script
creates a row in the `agents` table for each entry when an org is provisioned.
The `module` string points to the implementation package under `app/agents/` —
those are stubs for now and will be filled in per-agent.
"""

from dataclasses import dataclass, field


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


def is_implemented(agent_type: str) -> bool:
    for d in CATALOG:
        if d.type == agent_type:
            return d.implemented
    return False


CATALOG: list[AgentDef] = [
    AgentDef(
        type="project_status",
        display_name="Pace",
        name="Project Status Agent",
        tagline="Tracks milestones, delays, and delivery dates \u2014 surfaces project changes the moment they happen.",
        category="PMO",
        icon="chart",
        default_departments=("pmo",),
        module="app.agents.project_status",
    ),
    AgentDef(
        type="meeting_mom",
        display_name="Scribe",
        name="Meeting & MoM Agent",
        tagline="Captures every meeting: transcript, summary, action items, owners.",
        category="Productivity",
        icon="mic",
        default_departments=(),  # org-wide
        module="app.agents.meeting_mom",
    ),
    AgentDef(
        type="hr_service",
        display_name="Haven",
        name="HR Service Agent",
        tagline="Conversational assistant for leave, Form 16, compensation, and policy FAQs.",
        category="HR",
        icon="users",
        default_departments=("hr",),
        module="app.agents.hr_service",
    ),
    AgentDef(
        type="hiring_visibility",
        display_name="Scout",
        name="Hiring Visibility Agent",
        tagline="Unified view of the hiring pipeline \u2014 candidates, stages, interview load, time-to-offer.",
        category="Talent",
        icon="trending",
        default_departments=("talent",),
        module="app.agents.hiring_visibility",
    ),
    AgentDef(
        type="learning_journey",
        display_name="Mentor",
        name="Learning Journey Agent",
        tagline="Personalised training recommendations built from each person's role, skills, and reads.",
        category="L&D",
        icon="book",
        default_departments=("learning",),
        module="app.agents.learning_journey",
    ),
    AgentDef(
        type="vendor_identification",
        display_name="Ledger",
        name="Vendor Identification Agent",
        tagline="Parent-child vendor intelligence with spend optimisation and supplier matching.",
        category="Procurement",
        icon="box",
        default_departments=("procurement",),
        module="app.agents.vendor_identification",
    ),
    AgentDef(
        type="rnd_material_visibility",
        display_name="Atlas",
        name="R&D Material Visibility",
        tagline="Inventory and demand visibility across R&D and clinical teams.",
        category="R&D",
        icon="flask",
        default_departments=("rnd", "procurement"),
        module="app.agents.rnd_material_visibility",
    ),
    AgentDef(
        type="commercial_chatbot",
        display_name="Pitch",
        name="Commercial Insights Agent",
        tagline="Sales enablement \u2014 capability lookup, deck search, and reference pulls.",
        category="Commercial",
        icon="chat",
        default_departments=("commercial",),
        module="app.agents.commercial_chatbot",
    ),
    AgentDef(
        type="molecule_pipeline",
        display_name="Lens",
        name="Molecule Pipeline Intelligence",
        tagline="External market scanning: new molecules, competitor pipeline, trend signals.",
        category="Commercial",
        icon="pipeline",
        default_departments=("commercial_intel", "commercial"),
        module="app.agents.molecule_pipeline",
    ),
    AgentDef(
        type="fda_483_compliance",
        display_name="Aegis",
        name="483 FDA Compliance Agent",
        tagline="Reads 483 observations, pulls precedents, and drafts responses with citations.",
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
        tagline="Deviation intake, gap analysis, targeted Q&A, and compliant report drafting.",
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
        tagline="AI-powered categorisation of new records against your existing taxonomy.",
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
        tagline="Consolidates messy classifications into a clean master dataset, with reviewer overrides.",
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
        tagline="Enriches your records with attributes pulled from external reference sources.",
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
        tagline="Finds duplicates and near-duplicates across columns, AI-filtered for variants.",
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
        tagline="Per-column similarity scoring and weighted verdict for new-vs-reference checks.",
        category="Data Management",
        icon="search",
        default_departments=(),
        module="app.dma",
        implemented=True,
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
