"""Core data types for the CACM rule engine.

Why a separate module: the rule patterns, the orchestrator, and the API
serializers all share these shapes, so colocating them in one tiny file
avoids circular imports and gives every rule the same vocabulary.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import pandas as pd


@dataclass(frozen=True)
class KpiDef:
    """Declarative description of one KPI/KRI.

    Adding a KPI is appending a `KpiDef(...)` to `kpi_catalog.KPI_CATALOG`.
    The `pattern` field names a function in `rule_patterns.PATTERN_REGISTRY`;
    `params` is forwarded to that function verbatim.

    `rule_conditions` are short plain-English bullets shown on the wizard's
    Rule Engine stage *before* the rule fires. Keep them KPI-specific and
    declarative so an auditor can read them and understand exactly what
    will run.
    """
    type: str                          # unique slug, e.g. "po_after_invoice"
    process: str                       # display category, e.g. "Procurement"
    name: str                          # display name on the catalog tile
    description: str                   # one-liner for the catalog tile
    rule_objective: str                # longer prose shown on the run page
    source_tables: list[str]           # SAP-style table names, for the extract stage messages
    pattern: str                       # name of the rule pattern in PATTERN_REGISTRY
    params: dict[str, Any]             # forwarded verbatim to the pattern callable
    rule_conditions: list[str] = field(default_factory=list)  # plain-English bullets for the wizard


@dataclass
class RuleContext:
    """Container handed to a rule pattern at execution time.

    `tables` is keyed by the LOGICAL table name a pattern asks for (e.g.
    "ekko", "rbkp"); the orchestrator pre-loads them from sample data.
    """
    tables: dict[str, pd.DataFrame]
    kpi_type: str                      # forwarded so a pattern's error message can name itself


@dataclass
class ExceptionRecord:
    """One flagged exception. Patterns return a list of these.

    Stored as JSON in `cacm_exceptions.payload_json` — `to_payload` is the
    only serializer the orchestrator calls.
    """
    exception_no: str                  # e.g. "EX-0001"; assigned by the orchestrator after collection
    risk: str                          # "High" | "Medium" | "Low"
    reason: str                        # human-readable summary
    value: float | None = None         # numeric severity (e.g. dollar amount); optional
    fields: dict[str, Any] = field(default_factory=dict)  # key/value detail for the table

    def to_payload(self) -> dict[str, Any]:
        return {
            "exception_no": self.exception_no,
            "risk": self.risk,
            "reason": self.reason,
            "value": self.value,
            "fields": self.fields,
        }


# Common signature for a rule pattern callable.
PatternFn = Callable[[RuleContext, dict[str, Any]], list[ExceptionRecord]]
