"""Hardcoded "Recommended action" text per KPI.

Phase 1 of the AI-augmented exception flow: the demo ships with these
canned recommendations so leadership sees actionable guidance next to
each exception. A future story will swap this for an LLM call (one-line
change inside the orchestrator's enrich-exceptions step).

Tone is short imperative business-language guidance an audit team could
act on directly. Every entry must remain consistent with the KPI's
`type` slug in `kpi_catalog.KPI_CATALOG`.
"""
from __future__ import annotations


_RECS: dict[str, str] = {
    # ── Procurement ──────────────────────────────────────────────────────
    "po_after_invoice": (
        "Investigate why the PO was raised after the invoice; recover the "
        "approval trail and disable retroactive PO creation in workflow."
    ),

    # ── Inventory ────────────────────────────────────────────────────────
    "repeated_material_adjustments": (
        "Investigate the root cause of repeated adjustments (measurement "
        "error, theft, system-process mismatch); tighten cycle-count "
        "cadence and approval gate."
    ),
}


_DEFAULT = (
    "Investigate the flagged transaction with the process owner; document "
    "the resolution and file in the audit log for the period."
)


def recommendation_for(kpi_type: str) -> str:
    """Return the recommended action text for a KPI type, or the default fallback."""
    return _RECS.get(kpi_type, _DEFAULT)
