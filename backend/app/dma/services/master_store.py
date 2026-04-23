"""
Persistent Master Data Store
=============================
Read/write corrected master data to disk, organized by taxonomy key.

    backend/master/{taxonomy_key}/master.xlsx
    backend/master/{taxonomy_key}/meta.json
"""
from __future__ import annotations

import json
import pathlib
from datetime import datetime, timezone
from io import BytesIO

import pandas as pd

# app/dma/services/master_store.py → parents[3] = backend/
# Renamed from "master" to "dma_master" to avoid clashing with other data dirs.
MASTER_DIR = pathlib.Path(__file__).resolve().parents[3] / "dma_master"


def _ensure_dir(taxonomy_key: str) -> pathlib.Path:
    d = MASTER_DIR / taxonomy_key
    d.mkdir(parents=True, exist_ok=True)
    return d


def _master_path(taxonomy_key: str) -> pathlib.Path:
    return MASTER_DIR / taxonomy_key / "master.xlsx"


def _meta_path(taxonomy_key: str) -> pathlib.Path:
    return MASTER_DIR / taxonomy_key / "meta.json"


# ── Read ─────────────────────────────────────────────────────────────────

def load_master(taxonomy_key: str):
    """Load persisted master + metadata. Returns (DataFrame, meta_dict) or None."""
    mp = _master_path(taxonomy_key)
    if not mp.exists():
        return None
    df = pd.read_excel(mp)
    meta = {}
    mtp = _meta_path(taxonomy_key)
    if mtp.exists():
        try:
            meta = json.loads(mtp.read_text(encoding="utf-8"))
        except Exception:
            pass
    return df, meta


def list_available_masters() -> list[dict]:
    """Scan master directory and return info for each taxonomy key that has data."""
    if not MASTER_DIR.exists():
        return []
    result = []
    for d in sorted(MASTER_DIR.iterdir()):
        if not d.is_dir():
            continue
        mp = d / "master.xlsx"
        if not mp.exists():
            continue
        meta = {}
        mtp = d / "meta.json"
        if mtp.exists():
            try:
                meta = json.loads(mtp.read_text(encoding="utf-8"))
            except Exception:
                pass
        result.append({
            "key": d.name,
            "row_count": meta.get("row_count", 0),
            "last_updated": meta.get("last_updated", ""),
            "desc_col": meta.get("desc_col", ""),
            "class_col": meta.get("class_col", ""),
        })
    return result


# ── Write ────────────────────────────────────────────────────────────────

def save_master(
    taxonomy_key: str,
    df: pd.DataFrame,
    desc_col: str,
    class_col: str,
    po_col: str | None = None,
) -> dict:
    """Save DataFrame as master.xlsx + write meta.json. Returns meta dict."""
    _ensure_dir(taxonomy_key)
    df.to_excel(_master_path(taxonomy_key), index=False, engine="openpyxl")
    meta = {
        "taxonomy_key": taxonomy_key,
        "desc_col": desc_col,
        "class_col": class_col,
        "po_col": po_col or "",
        "row_count": len(df),
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }
    _meta_path(taxonomy_key).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8",
    )
    return meta


def append_to_master(
    taxonomy_key: str,
    new_rows: pd.DataFrame,
    desc_col: str,
    class_col: str,
    po_col: str | None = None,
) -> tuple[pd.DataFrame, dict]:
    """Append rows to existing master (or create if none). Returns (merged_df, meta)."""
    existing = load_master(taxonomy_key)
    if existing is not None:
        old_df, old_meta = existing
        # Use column info from existing meta if available
        desc_col = old_meta.get("desc_col", desc_col)
        class_col = old_meta.get("class_col", class_col)
        po_col = old_meta.get("po_col", po_col) or po_col
        merged = pd.concat([old_df, new_rows], ignore_index=True)
    else:
        merged = new_rows.copy()
    meta = save_master(taxonomy_key, merged, desc_col, class_col, po_col)
    return merged, meta


def download_master_bytes(taxonomy_key: str) -> bytes | None:
    """Return master Excel as bytes, or None if not found."""
    mp = _master_path(taxonomy_key)
    if not mp.exists():
        return None
    return mp.read_bytes()
