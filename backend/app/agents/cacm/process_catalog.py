"""Process catalog — declarative listing of CACM business processes and their
KRIs. Drives the Process Picker screen between the Agent Hub and the KRI
run page.

Each process is a top-level audit area (e.g. Procurement to Payment); each
KRI within a process maps to a `kpi_type` in `KPI_CATALOG`. Two real KPIs
are implemented (`po_after_invoice`, `repeated_material_adjustments`); the
remaining KRIs map to one of those by domain affinity so the demo flow
works end-to-end for every tile.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# Procurement-to-Payment KRIs map here; default for non-inventory processes too.
_DEFAULT_KPI = "po_after_invoice"
# Inventory-Management KRIs map here.
_INVENTORY_KPI = "repeated_material_adjustments"


@dataclass(frozen=True)
class KriSummary:
    name: str
    kpi_type: str


@dataclass(frozen=True)
class ProcessDef:
    key: str
    name: str
    intro: str
    kris: list[KriSummary] = field(default_factory=list)


# ── Catalog ──────────────────────────────────────────────────────────────────

PROCESS_CATALOG: list[ProcessDef] = [
    ProcessDef(
        key="contract_to_cash",
        name="Contract to Cash",
        intro=(
            "Monitors revenue leakage, billing irregularities, customer credit "
            "risks, and order-to-cash process compliance across the sales "
            "lifecycle."
        ),
        kris=[
            KriSummary(name="Revenue recognized before service completion (cut-off breaches)", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Discounts or rate overrides beyond approval limits", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Revenue reversals in subsequent periods", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Duplicate billing or missed billing instances", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Concentration of revenue from single customer", kpi_type=_DEFAULT_KPI),
        ],
    ),
    ProcessDef(
        key="procurement_to_payment",
        name="Procurement to Payment",
        intro=(
            "Identifies procurement and payment control gaps including "
            "unauthorized purchases, duplicate payments, split POs, and "
            "approval bypass scenarios."
        ),
        kris=[
            KriSummary(name="PO issued after invoice date (retroactive approvals)", kpi_type="po_after_invoice"),
            KriSummary(name="% of non-PO based purchases", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Vendor master changes without dual approval", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Multiple vendors with same bank account / address", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Split POs to bypass approval thresholds", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Duplicate invoices processed", kpi_type=_DEFAULT_KPI),
        ],
    ),
    ProcessDef(
        key="inventory_management",
        name="Inventory Management",
        intro=(
            "Detects inventory inaccuracies, stock mismatches, unusual "
            "write-offs, obsolescence risks, and movement anomalies across "
            "warehouses and systems."
        ),
        kris=[
            KriSummary(name="Repeated adjustments for same materials", kpi_type="repeated_material_adjustments"),
            KriSummary(name="Excessive emergency stock usage", kpi_type=_INVENTORY_KPI),
            KriSummary(name="High inventory shrinkage / adjustments", kpi_type=_INVENTORY_KPI),
            KriSummary(name="Slow-moving / obsolete inventory %", kpi_type=_INVENTORY_KPI),
            KriSummary(name="Frequent manual inventory write-offs", kpi_type=_INVENTORY_KPI),
            KriSummary(name="Inventory issued without approved requisition", kpi_type=_INVENTORY_KPI),
            KriSummary(name="Mismatch between physical vs system count", kpi_type=_INVENTORY_KPI),
        ],
    ),
    ProcessDef(
        key="budgeting_planning",
        name="Budgeting & Planning",
        intro=(
            "Evaluates budgeting accuracy, forecast reliability, variance "
            "trends, and manual adjustment risks impacting financial planning "
            "processes."
        ),
        kris=[
            KriSummary(name="Significant variance between budget vs actual (> threshold)", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Forecast vs actual variance %", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Budget changes post approval", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Manual adjustments near period-end", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Duplicate or inconsistent budget entries", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Unauthorized budget modifications", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Cost center budget overruns", kpi_type=_DEFAULT_KPI),
        ],
    ),
    ProcessDef(
        key="accounts_payables",
        name="Accounts Payables",
        intro=(
            "Monitors invoice processing controls, vendor payment compliance, "
            "duplicate invoices, three-way match exceptions, and inactive "
            "vendor transactions."
        ),
        kris=[
            KriSummary(name="Invoices processed without PO / contract", kpi_type=_DEFAULT_KPI),
            KriSummary(name="GRN-to-invoice mismatch rates", kpi_type=_DEFAULT_KPI),
            KriSummary(name="High volume of manual journal adjustments in AP", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Payments to inactive / blacklisted vendors", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Changes in vendor bank details before payment", kpi_type=_DEFAULT_KPI),
        ],
    ),
    ProcessDef(
        key="hr_payroll",
        name="HR & Payroll",
        intro=(
            "Identifies payroll anomalies including ghost employees, duplicate "
            "payments, unauthorized allowances, reimbursement abuse, and "
            "segregation of duties conflicts."
        ),
        kris=[
            KriSummary(name="Payments to inactive / terminated employees", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Payroll processed without approved timesheets", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Ghost employees (no attendance / activity logs)", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Multiple employees sharing same bank account", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Excessive allowances or reimbursements", kpi_type=_DEFAULT_KPI),
        ],
    ),
    ProcessDef(
        key="fixed_assets",
        name="Fixed Assets",
        intro=(
            "Tracks asset capitalization, depreciation accuracy, retirement "
            "compliance, insurance coverage, and asset utilization "
            "irregularities."
        ),
        kris=[
            KriSummary(
                name="Different depreciation % and/or remaining life assigned to same type / category of assets",
                kpi_type=_DEFAULT_KPI,
            ),
            KriSummary(name="Fixed assets not covered under Insurance", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Month-on-month variance in total depreciation", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Variance in depreciation start date and asset capitalization date", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Duplicate fixed asset records", kpi_type=_DEFAULT_KPI),
            KriSummary(name="High aging of Capital WIP", kpi_type=_DEFAULT_KPI),
        ],
    ),
    ProcessDef(
        key="it",
        name="IT",
        intro=(
            "Continuously monitors privileged access, segregation of duties "
            "violations, password policy compliance, user access governance, "
            "and patch management controls."
        ),
        kris=[
            KriSummary(name="Privileged accounts not logged in for >30/60/90 days", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Users terminated but active in AD/ERP", kpi_type=_DEFAULT_KPI),
            KriSummary(name="SOD Violations", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Accounts not complying with password expiry policy", kpi_type=_DEFAULT_KPI),
            KriSummary(name="Critical patches not applied within SLA", kpi_type=_DEFAULT_KPI),
            KriSummary(name="% of scheduled backups failed in last cycle", kpi_type=_DEFAULT_KPI),
        ],
    ),
]


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_processes() -> list[ProcessDef]:
    """Full process catalog in declared order."""
    return list(PROCESS_CATALOG)


def get_process(key: str) -> ProcessDef | None:
    """Look up a single process by its key, or None if no match."""
    for p in PROCESS_CATALOG:
        if p.key == key:
            return p
    return None
