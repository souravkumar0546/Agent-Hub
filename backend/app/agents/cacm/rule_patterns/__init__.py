"""Pattern registry — maps pattern name → callable.

Each pattern has signature `(ctx: RuleContext, params: dict) -> list[ExceptionRecord]`.
A KPI in the catalog declares its pattern by name; the orchestrator looks it up here.
"""
from __future__ import annotations

from app.agents.cacm.types import PatternFn
from app.agents.cacm.rule_patterns.row_threshold import row_threshold
from app.agents.cacm.rule_patterns.fuzzy_duplicate import fuzzy_duplicate
from app.agents.cacm.rule_patterns.date_compare import date_compare
from app.agents.cacm.rule_patterns.aggregate_threshold import aggregate_threshold
from app.agents.cacm.rule_patterns.cross_table_compare import cross_table_compare
from app.agents.cacm.rule_patterns.missing_reference import missing_reference
from app.agents.cacm.rule_patterns.temporal_anomaly import temporal_anomaly


PATTERN_REGISTRY: dict[str, PatternFn] = {
    "row_threshold": row_threshold,
    "fuzzy_duplicate": fuzzy_duplicate,
    "date_compare": date_compare,
    "aggregate_threshold": aggregate_threshold,
    "cross_table_compare": cross_table_compare,
    "missing_reference": missing_reference,
    "temporal_anomaly": temporal_anomaly,
}
