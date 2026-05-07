"""KPI/KRI catalog — one KpiDef per row in design spec §3.

CACM v1 ships with a trimmed scope of 2 KPIs (Procurement + Inventory) so
the demo flow can be exercised end-to-end without a 40-KPI rollout. The
remaining catalog entries (38 KPIs across AP / GL / Payroll / Sales /
Access / Insurance) were dropped from v1 and may return in later releases.

Adding a KPI: append a KpiDef(...) to the relevant process block below and
re-export from `KPI_CATALOG`. Removing a KPI: delete the line. The catalog
drives the Library page rendering, the rule engine dispatch, and per-KPI
smoke tests.

Some KPIs reference logical / derived tables (e.g. `po_invoice_joined`,
`mseg_adjustments`) that the orchestrator (Task 22) materializes by joining
or filtering the raw SAP-style tables before pattern dispatch.
"""
from __future__ import annotations

from app.agents.cacm.types import KpiDef


# ── Procurement (1) ──────────────────────────────────────────────────────────

PROCUREMENT_KPIS: list[KpiDef] = [
    KpiDef(
        type="po_after_invoice",
        process="Procurement",
        name="PO Created After Invoice Date",
        description="Procurement approval should occur before invoice processing.",
        rule_objective=(
            "Compare PO creation date with the corresponding invoice posting date. "
            "If the PO is dated AFTER the invoice, it suggests the PO was raised "
            "retroactively — a red flag for procurement controls."
        ),
        source_tables=["EKBE", "EKKO", "EKPO", "EBAN", "T5VS5"],
        pattern="date_compare",
        params={
            "table": "po_invoice_joined",
            "left_date": "po_created",
            "right_date": "invoice_posted",
            "op": ">",
            "risk_bands": [(0, 3, "Low"), (4, 14, "Medium"), (15, None, "High")],
            "reason_template": "PO {po_no} created {diff_days} days after invoice {inv_no}",
            # Surface the rich payload columns the exception report needs.
            "fields": [
                "po_no",
                "inv_no",
                "vendor_code",
                "company_code",
                "location",
                "po_line_item",
                "po_created",
                "invoice_posted",
                "po_created_by",
                "invoice_created_by",
                "po_amount",
                "invoice_amount",
                "po_approval_status",
            ],
        },
        rule_conditions=[
            "Tables in scope: EKBE, EKKO, EKPO, EBAN, T5VS5",
            "Filter EKBE rows where BEWTP = 'Q' (invoice receipt) AND goods movement type is not null",
            "Map purchasing documents to invoices using EKPO.EBELN + EKPO.EBELP",
            "Flag cases where EKKO.AEDAT (PO Created on) > EKBE.BLDAT (Invoice document date)",
            "Per the standard process the Invoice date should fall after the PO creation date — transactions that don't follow this surface as exceptions.",
        ],
    ),
]


# ── Inventory (1) ────────────────────────────────────────────────────────────

INVENTORY_KPIS: list[KpiDef] = [
    KpiDef(
        type="repeated_material_adjustments",
        process="Inventory",
        name="Repeated Adjustments for Same Materials",
        description="Materials with frequent inventory adjustments — typical control-weakness signal.",
        rule_objective=(
            "Group MSEG inventory movements by material and count adjustment "
            "movements (movement type 309 / 561 / 562 / 701 / 702 etc.). Flag "
            "materials with more than 3 adjustment movements in the period — "
            "indicates a process or measurement control gap."
        ),
        source_tables=["MSEG", "MARA"],
        pattern="aggregate_threshold",
        params={
            "table": "mseg_adjustments",
            "group_by": ["material_id"],
            "agg": {"column": "doc_no", "fn": "count"},
            "op": ">",
            "threshold": 3,
            "as_fraction": False,
            "risk": [(4, 5, "Low"), (6, 9, "Medium"), (10, None, "High")],
            "reason_template": "Material {key} has {value:.0f} adjustment movements",
            "fields": [],
        },
        rule_conditions=[
            "Aggregate MSEG inventory movements grouped by material_id, count adjustment movements (movement types 309 / 561 / 562 / 701 / 702) and flag any material with more than 3 adjustments in the period.",
        ],
    ),
]


# ── Master catalog ───────────────────────────────────────────────────────────

KPI_CATALOG: list[KpiDef] = [
    *PROCUREMENT_KPIS,
    *INVENTORY_KPIS,
]


def kpi_by_type(t: str) -> KpiDef | None:
    """Linear scan — catalog is small so a dict cache adds no value."""
    for k in KPI_CATALOG:
        if k.type == t:
            return k
    return None


def kpis_by_process() -> dict[str, list[KpiDef]]:
    """Group catalog by process name; preserves declaration order within each group."""
    out: dict[str, list[KpiDef]] = {}
    for k in KPI_CATALOG:
        out.setdefault(k.process, []).append(k)
    return out
