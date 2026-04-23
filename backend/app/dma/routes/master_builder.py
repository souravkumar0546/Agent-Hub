"""Master Builder Agent — fix inconsistent master data and persist to disk."""
from __future__ import annotations

import json
import uuid
from io import BytesIO
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.dma.services.classification_service import (
    build_download_bytes,
    fix_master_data,
    set_taxonomy,
)
from app.dma.services.master_store import (
    append_to_master,
    download_master_bytes,
    list_available_masters,
    load_master,
    save_master,
)

router = APIRouter(tags=["master-builder"])

# Temporary store for review — holds fixed data until user confirms "Add to Master"
_review_store: dict[str, dict] = {}


def _read_table(raw: bytes) -> pd.DataFrame:
    bio = BytesIO(raw)
    try:
        return pd.read_excel(bio)
    except Exception:
        bio.seek(0)
        return pd.read_csv(bio)


@router.post("/master-builder/fix-master")
async def master_builder_fix(
    file: UploadFile = File(...),
    desc_col: str = Form(...),
    class_col: str = Form(...),
    po_col: str = Form(""),
    status_col: str = Form(""),
    sim_threshold: float = Form(0.65),
    ai_batch_size: int = Form(5),
    taxonomy_key: str = Form("ZSC1"),
) -> dict:
    """Fix master data and return for review — does NOT save to disk yet."""
    try:
        df = _read_table(await file.read())
    except Exception as exc:
        raise HTTPException(400, f"Could not read file: {exc}")
    if desc_col not in df.columns or class_col not in df.columns:
        raise HTTPException(400, "Invalid desc/class column")
    po = po_col if po_col and po_col in df.columns else None
    status = status_col if status_col and status_col in df.columns else None

    set_taxonomy({"taxonomy_key": taxonomy_key})
    fixed_df, summary = await fix_master_data(
        df, desc_col, class_col, po, status, float(sim_threshold), int(ai_batch_size),
    )

    # Store for review — user must click "Add to Master" to persist
    review_id = uuid.uuid4().hex[:12]
    _review_store[review_id] = {
        "df": fixed_df,
        "desc_col": desc_col,
        "class_col": class_col,
        "po_col": po,
        "taxonomy_key": taxonomy_key,
    }

    rows = fixed_df.fillna("").astype(str).to_dict(orient="records")
    columns = list(fixed_df.columns)
    changed = summary.get("changed_row_indices", [])

    return {
        "summary": summary,
        "rows": rows,
        "columns": columns,
        "changed_row_indices": changed,
        "taxonomy_key": taxonomy_key,
        "review_id": review_id,
    }


@router.post("/master-builder/add-to-master")
async def master_builder_add_to_master(
    review_id: str = Form(...),
    # Optional client-side overrides the reviewer made via the dropdown on
    # each row. Wire format: a JSON-encoded object of the form
    #     { "<row_index>": "<new category>" }
    # where `row_index` is the zero-based position within the dataframe's
    # current row order (same index the client sees as `rows[i]`). Values
    # are validated against the row's class column; unknown / empty
    # entries are silently ignored so a noisy client can't corrupt master.
    overrides: str | None = Form(default=None),
) -> dict:
    """Persist reviewed fixed data to disk master.

    Merges 'New Classification' into class_col, applies any user overrides
    sent from the review UI (so reviewers who disagree with the AI's fix
    get their choice written instead), drops the temp column, and appends.
    """
    if review_id not in _review_store:
        raise HTTPException(404, "Review data expired or not found. Please re-run Fix Master.")
    store = _review_store.pop(review_id)
    df = store["df"]
    desc_col = store["desc_col"]
    class_col = store["class_col"]
    po_col = store["po_col"]
    taxonomy_key = store["taxonomy_key"]

    # Merge "New Classification" into class_col: where new is non-empty, use it
    new_col = "New Classification"
    if new_col in df.columns:
        for i in range(len(df)):
            new_val = str(df.iloc[i][new_col]).strip()
            if new_val:
                df.at[df.index[i], class_col] = new_val
        df = df.drop(columns=[new_col])

    # Apply reviewer overrides last so they win over both the original
    # class and any AI-suggested "New Classification". Parse defensively —
    # a malformed JSON string or a wrong-typed payload is treated as "no
    # overrides" rather than a 500.
    if overrides:
        try:
            parsed = json.loads(overrides)
        except Exception:
            parsed = None
        if isinstance(parsed, dict):
            for raw_idx, new_val in parsed.items():
                try:
                    i = int(raw_idx)
                except (TypeError, ValueError):
                    continue
                if not (0 <= i < len(df)):
                    continue
                val = str(new_val or "").strip()
                if not val:
                    continue
                df.at[df.index[i], class_col] = val

    # Append to existing master on disk (or create if none)
    merged_df, meta = append_to_master(taxonomy_key, df, desc_col, class_col, po_col)

    return {
        "ok": True,
        "taxonomy_key": taxonomy_key,
        "total_master_rows": len(merged_df),
    }


@router.get("/master-builder/masters")
async def master_builder_list() -> list[dict]:
    return list_available_masters()


@router.get("/master-builder/masters/{taxonomy_key}")
async def master_builder_get(taxonomy_key: str) -> dict:
    result = load_master(taxonomy_key)
    if result is None:
        raise HTTPException(404, f"No master data found for {taxonomy_key}")
    df, meta = result
    rows = df.head(500).fillna("").astype(str).to_dict(orient="records")
    return {
        "meta": meta,
        "columns": list(df.columns),
        "rows": rows,
        "total_rows": len(df),
    }


@router.get("/master-builder/masters/{taxonomy_key}/download")
async def master_builder_download(taxonomy_key: str):
    data = download_master_bytes(taxonomy_key)
    if data is None:
        raise HTTPException(404, f"No master data found for {taxonomy_key}")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=master_{taxonomy_key}.xlsx"},
    )
