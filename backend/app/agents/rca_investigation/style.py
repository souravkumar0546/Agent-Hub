"""Style-example retrieval from real Syngene deviation reports.

Loads DOCX/DOC examples from `backend/data/examples/` and returns clean section
content matching a given field, for use as a Phase 2 writing style reference.

Ported from Devio generation/style.py + knowledge/loader.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.config import settings
from app.agents.rca_investigation.file_extractor import extract_doc, extract_docx, extract_pdf


SECTION_HEADERS = [
    "SOURCE OF NON-CONFORMITY",
    "DESCRIPTION OF THE NON-CONFORMITY",
    "Description:",
    "Reference Documents/Instruments/Equipment/Products",
    "Initiator Name and Department",
    "INVESTIGATION TEAM",
    "PRE-EVALUATION",
    "Initial/Preliminary Impact",
    "Immediate Actions or Correction",
    "Historical Check",
    "INVESTIGATION:",
    "Root Cause Analysis",
    "Why?",
    "Brainstorming",
    "Procedural Evaluation",
    "Personnel Evaluation",
    "Summary of data and documents",
    "LIST OF ROOT CAUSES",
    "Evaluation of root cause with historical",
    "IMPACT ASSESSMENT",
    "Impact on the quality",
    "Impact on other products",
    "Impact on other batches",
    "Impact on quality management",
    "Impact on Validated state",
    "Impact on preventive maintenance",
    "CORRECTIVE AND PREVENTIVE",
    "CONCLUSION",
    "ATTACHMENTS",
    "ABBREVIATIONS",
    "INVESTIGATION TEAM SIGNATURES",
    "Sequence of events",
    "Sequence of Events",
    "REVISION HISTORY",
]


FIELD_TO_SECTION_KEYWORDS = {
    "description": ["Description:"],
    "reference_docs": ["Reference Documents/Instruments/Equipment"],
    "initiator": ["Initiator Name and Department"],
    "preliminary_impact": ["Initial/Preliminary Impact", "Preliminary Impact assessment"],
    "immediate_actions": ["Immediate Actions or Correction"],
    "historical_data_source": ["Historical Check"],
    "historical_timeframe": ["Historical Check"],
    "historical_similar_events": ["Historical Check"],
    "investigation_team": ["INVESTIGATION TEAM"],
    "sequence_of_events": ["Sequence of events", "Sequence of Events"],
    "five_why": ["Why?", "Why-Why analysis", "5-WHY"],
    "brainstorming": ["Brainstorming"],
    "fishbone": ["Fish bone", "Fishbone", "Cause and Effect"],
    "process_mapping": ["Process Mapping", "Gap Analysis", "Procedural Evaluation"],
    "root_causes": ["LIST OF ROOT CAUSES", "Root causes and contributing"],
    "data_summary": ["Summary of data and documents"],
    "historical_root_cause_eval": ["Evaluation of root cause with historical"],
    "impact_product_quality": ["Impact on the quality of the product"],
    "impact_other_products": ["Impact on other products"],
    "impact_other_batches": ["Impact on other batches"],
    "impact_qms_regulatory": ["Impact on quality management", "Impact on QMS"],
    "impact_validated_state": ["Impact on Validated state"],
    "impact_pm_calibration": ["Impact on preventive maintenance"],
    "corrections": ["CORRECTIVE AND PREVENTIVE"],
    "corrective_actions": ["CORRECTIVE AND PREVENTIVE"],
    "preventive_actions": ["CORRECTIVE AND PREVENTIVE"],
    "conclusion": ["CONCLUSION"],
}


@dataclass
class DeviationExample:
    filename: str
    full_text: str
    sections: dict[str, str] = field(default_factory=dict)


def _is_clean(line: str) -> bool:
    return "HYPERLINK" not in line and "PAGEREF" not in line and "TOC \\" not in line


def _extract_section(full_text: str, section_keywords: list[str], max_chars: int) -> str:
    lines = full_text.split("\n")

    start_idx = None
    for i, line in enumerate(lines):
        if not _is_clean(line):
            continue
        for kw in section_keywords:
            if kw.lower() in line.lower():
                start_idx = i + 1
                break
        if start_idx is not None:
            break

    if start_idx is None:
        return ""

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if not _is_clean(lines[i]):
            continue
        stripped = lines[i].strip()
        if not stripped:
            continue
        for header in SECTION_HEADERS:
            if header.lower() in stripped.lower() and header.lower() not in [k.lower() for k in section_keywords]:
                end_idx = i
                break
        if end_idx != len(lines):
            break

    section_lines = [l for l in lines[start_idx:end_idx] if _is_clean(l)]
    return "\n".join(section_lines).strip()[:max_chars]


def _load_examples() -> list[DeviationExample]:
    examples: list[DeviationExample] = []
    examples_dir: Path = settings.examples_dir
    if not examples_dir.exists():
        return examples
    for filepath in sorted(examples_dir.iterdir()):
        if filepath.name.startswith("."):
            continue
        suffix = filepath.suffix.lower()
        text = ""
        try:
            if suffix == ".docx":
                text = extract_docx(filepath)
            elif suffix == ".doc":
                text = extract_doc(filepath)
            elif suffix == ".pdf":
                text = extract_pdf(filepath)
        except Exception as e:  # don't let one bad file break all style lookups
            print(f"[style] failed to read {filepath.name}: {e}")
            continue
        if text:
            examples.append(DeviationExample(filename=filepath.name, full_text=text))
    return examples


_examples_cache: list[DeviationExample] | None = None


def get_examples() -> list[DeviationExample]:
    global _examples_cache
    if _examples_cache is None:
        _examples_cache = _load_examples()
    return _examples_cache


def get_style_examples_for_section(field_id: str, max_chars: int = 1500) -> str:
    examples = get_examples()
    if not examples:
        return ""
    keywords = FIELD_TO_SECTION_KEYWORDS.get(field_id, [])
    if not keywords:
        return ""

    per_example = max_chars // max(len(examples), 1)
    chunks: list[str] = []
    for ex in examples:
        section_text = _extract_section(ex.full_text, keywords, per_example)
        if section_text and len(section_text) > 30:
            chunks.append(f"[{ex.filename}]:\n{section_text}")

    if not chunks:
        return ""
    return "\n\n---\n\n".join(chunks)[:max_chars]
