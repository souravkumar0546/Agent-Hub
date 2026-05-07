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
            "Review invoice receipt transactions from Purchasing Document History (EKBE) where the PO History Category indicates Invoice Receipt.",
            "Match vendor invoices with the corresponding Purchase Orders and PO line items using Purchasing Document Item (EKPO).",
            "Retrieve Purchase Order header details and PO Creation Date from Purchasing Document Header (EKKO).",
            "Refer Purchase Requisition details from Purchase Requisition (EBAN), where applicable.",
            "Use Tax and Language Reference Details (T5VS5) for supporting tax and localization reference information.",
            "Compare the Vendor Invoice Date from Purchasing Document History (EKBE.BLDAT) with the Purchase Order Creation Date from Purchasing Document Header (EKKO.AEDAT).",
            "Identify cases where the Vendor Invoice Date is earlier than the PO Creation Date.",
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
            "The KPI highlights repeated inventory adjustments for the same "
            "materials, which may indicate weak inventory controls, stock "
            "inaccuracies, manual intervention, process gaps, or potential "
            "manipulation of inventory records."
        ),
        source_tables=["MKPF", "MSEG", "MARA", "MBEW", "T001W", "T156", "T023"],
        pattern="aggregate_threshold",
        params={
            "table": "mseg_adjustments",
            "group_by": ["material_id"],
            "agg": {"column": "doc_no", "fn": "count"},
            "op": ">",
            "threshold": 3,
            "as_fraction": False,
            "risk": [(4, 5, "Low"), (6, 9, "Medium"), (10, None, "High")],
            "reason_template": "Material {material_id} ({material_name}) has {value:.0f} adjustment movements",
            "fields": [],
            "metadata_fields": [
                "company_code", "werks", "lgort", "material_id", "material_name",
                "material_group", "movement_type", "doc_no", "line_item",
                "posting_date", "quantity", "unit_of_measure", "adjustment_amount",
                "user_id", "reversal_indicator",
            ],
        },
        rule_conditions=[
            "Filter inventory adjustment transactions from MSEG using relevant movement types (stock adjustments, inventory corrections, write-offs, reversals, manual stock postings).",
            "Map inventory adjustment transactions using Material Number (MSEG.MATNR), Plant (MSEG.WERKS), Storage Location (MSEG.LGORT), and Posting Date (MKPF.BUDAT).",
            "Identify cases where the same material has multiple adjustment postings within a defined monitoring period.",
            "Flag materials where repeated reversals and repostings occur for the same material and quantity pattern.",
            "Exclude system-generated or approved periodic inventory adjustment entries, wherever applicable.",
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
