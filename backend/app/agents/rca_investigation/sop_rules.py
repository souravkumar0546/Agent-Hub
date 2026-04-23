"""SOP-GMP-QA-0066 compliance rules.

Hardcoded checks enforced in code, not left to the LLM. Ported from Devio.
"""

from __future__ import annotations

from app.agents.rca_investigation.session_state import Session
from app.agents.rca_investigation.template import FieldStatus


def validate_sop_compliance(session: Session) -> list[str]:
    warnings: list[str] = []
    fields = session.fields

    # SOP 7.4.3.1: Historical check >= 12 months
    timeframe = fields.get("historical_timeframe")
    justification = fields.get("historical_justification")
    if timeframe and timeframe.value:
        text = timeframe.value.lower()
        short_periods = ["6 month", "3 month", "1 month", "6month", "3month"]
        if any(p in text for p in short_periods) and (
            not justification or not justification.value
        ):
            warnings.append(
                "SOP 7.4.3.1: Historical check period appears to be less than 12 months. "
                "A justification is required for review periods shorter than 12 months."
            )

    # SOP 7.8.6: Conclusion requires root cause
    root_causes = fields.get("root_causes")
    conclusion = fields.get("conclusion")
    if (
        conclusion
        and conclusion.status in (FieldStatus.FILLED, FieldStatus.PARTIAL)
        and (not root_causes or root_causes.status == FieldStatus.EMPTY)
    ):
        warnings.append(
            "SOP 7.8.6: Investigation cannot be closed without identifying "
            "a definite or probable root cause."
        )

    # SOP 7.7.1: CAPA required once root cause exists
    corrective = fields.get("corrective_actions")
    preventive = fields.get("preventive_actions")
    if (
        root_causes
        and root_causes.status == FieldStatus.FILLED
        and (
            (not corrective or corrective.status == FieldStatus.EMPTY)
            and (not preventive or preventive.status == FieldStatus.EMPTY)
        )
    ):
        warnings.append(
            "SOP 7.7.1: Root cause has been identified but no CAPA (corrective or "
            "preventive actions) has been proposed yet."
        )

    # SOP 7.5.11.5: Human error needs systemic investigation
    if root_causes and root_causes.value:
        lower_rc = root_causes.value.lower()
        if "human error" in lower_rc or "operator error" in lower_rc:
            if "systemic" not in lower_rc and "system" not in lower_rc:
                warnings.append(
                    "SOP 7.5.11.5: Human error identified as root cause. "
                    "Further investigation needed to identify systemic/process/procedural "
                    "gaps that contributed to the error."
                )

    # SOP 7.6.4: Major/Critical needs full impact assessment
    category = fields.get("source_category")
    if category and category.value.lower() in ("major", "critical"):
        impact_fields = [
            "impact_product_quality",
            "impact_other_products",
            "impact_other_batches",
            "impact_qms_regulatory",
            "impact_validated_state",
            "impact_pm_calibration",
        ]
        empty_impacts = [
            fid for fid in impact_fields
            if fields.get(fid) and fields[fid].status == FieldStatus.EMPTY
        ]
        if empty_impacts and root_causes and root_causes.status == FieldStatus.FILLED:
            warnings.append(
                f"SOP 7.6.4: For {category.value} deviations, all impact assessment "
                f"areas must be addressed. Missing: {len(empty_impacts)} of 6 sections."
            )

    return warnings
