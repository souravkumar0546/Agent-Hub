"""Classification Agent — classify new materials against persisted master data."""
from __future__ import annotations

import json
from io import BytesIO
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.dma.services.classification_service import (
    ai_classify_new,
    classify_batch,
    classify_new_material,
    set_taxonomy,
)
from app.dma.services.master_store import append_to_master, load_master, save_master

router = APIRouter(tags=["classify"])


def _read_table(raw: bytes) -> pd.DataFrame:
    bio = BytesIO(raw)
    try:
        return pd.read_excel(bio)
    except Exception:
        bio.seek(0)
        return pd.read_csv(bio)


@router.post("/classify/single")
async def classify_single(
    taxonomy_key: str = Form(...),
    input_values_json: str = Form(...),
    sim_threshold: float = Form(0.65),
) -> dict:
    try:
        inputs = json.loads(input_values_json)
    except Exception as exc:
        raise HTTPException(400, f"Invalid input_values_json: {exc}")

    set_taxonomy({"taxonomy_key": taxonomy_key})

    result = load_master(taxonomy_key)
    if result is not None:
        df_master, meta = result
        desc_col = meta.get("desc_col", "")
        class_col = meta.get("class_col", "")
        if desc_col and class_col:
            return await classify_new_material(
                df_master, desc_col, class_col,
                {str(k): str(v) for k, v in inputs.items()},
                float(sim_threshold),
            )

    # No master — classify purely from taxonomy definitions via AI
    desc_value = " ".join(str(v) for v in inputs.values() if str(v).strip())
    po_value = ""
    keys = list(inputs.keys())
    if len(keys) >= 1:
        desc_value = str(inputs[keys[0]]).strip()
    if len(keys) >= 2:
        po_value = str(inputs[keys[1]]).strip()
    ai_result = await ai_classify_new(desc_value, po_value)
    return {
        "assigned_category": ai_result.get("category", "UNKNOWN"),
        "method": "ai_new_classification",
        "reasoning": ai_result.get("reasoning", ""),
        "matched_rows": [],
    }


@router.post("/classify/batch")
async def classify_batch_endpoint(
    taxonomy_key: str = Form(...),
    file: UploadFile = File(...),
    desc_col: str = Form(...),
    po_col: str = Form(""),
    sim_threshold: float = Form(0.65),
) -> dict:
    try:
        df_new = _read_table(await file.read())
    except Exception as exc:
        raise HTTPException(400, f"Could not read file: {exc}")
    if desc_col not in df_new.columns:
        raise HTTPException(400, f"Column '{desc_col}' not found in uploaded file")

    set_taxonomy({"taxonomy_key": taxonomy_key})

    master_result = load_master(taxonomy_key)
    has_master = master_result is not None
    if has_master:
        df_master, meta = master_result
        master_desc_col = meta.get("desc_col", desc_col)
        master_class_col = meta.get("class_col", "Classification")
    else:
        master_desc_col = desc_col
        master_class_col = "Classification"

    # Build item dicts from uploaded rows
    items = []
    for _, row in df_new.iterrows():
        item = {master_desc_col: str(row.get(desc_col, "")).strip()}
        if po_col and po_col in df_new.columns:
            po_key = meta.get("po_col", "PO Text") if has_master else "PO Text"
            item[po_key] = str(row.get(po_col, "")).strip()
        items.append(item)

    if has_master:
        results = await classify_batch(
            df_master, master_desc_col, master_class_col, items, float(sim_threshold),
        )
    else:
        # No master — classify each item purely via AI
        results = []
        for item in items:
            desc_value = str(item.get(master_desc_col, "")).strip()
            po_value = " ".join(str(v) for k, v in item.items() if k != master_desc_col and str(v).strip())
            if not desc_value:
                results.append({"assigned_category": "UNKNOWN", "method": "empty_input", "reasoning": "Empty input", "matched_rows": []})
                continue
            ai_result = await ai_classify_new(desc_value, po_value)
            results.append({
                "assigned_category": ai_result.get("category", "UNKNOWN"),
                "method": "ai_new_classification",
                "reasoning": ai_result.get("reasoning", ""),
                "matched_rows": [],
            })

    # Attach original row data + classification to each result
    po_key = meta.get("po_col", "PO Text") if has_master else "PO Text"
    original_rows = df_new.fillna("").astype(str).to_dict(orient="records")
    for i, r in enumerate(results):
        r["row_index"] = i
        r["input_description"] = items[i].get(master_desc_col, "")
        r["input_po"] = items[i].get(po_key, "")
        r["original_row"] = original_rows[i] if i < len(original_rows) else {}

    return {
        "results": results,
        "total": len(results),
        "columns": list(df_new.columns),
    }


@router.post("/classify/add-to-master")
async def classify_add_to_master(
    taxonomy_key: str = Form(...),
    rows_json: str = Form(...),
) -> dict:
    try:
        rows = json.loads(rows_json)
        if not isinstance(rows, list):
            raise ValueError("rows_json must be an array")
    except Exception as exc:
        raise HTTPException(400, f"Invalid rows_json: {exc}")

    new_df = pd.DataFrame(rows)

    # Standard columns used by Classification Agent
    DESC_COL = "Material Description"
    CLASS_COL = "Classification"
    PO_COL = "PO Text"

    result = load_master(taxonomy_key)
    if result is not None:
        _, meta = result
        desc_col = meta.get("desc_col", DESC_COL)
        class_col = meta.get("class_col", CLASS_COL)
        po_col = meta.get("po_col", PO_COL)
        # Map standard columns to whatever the master uses
        rename = {}
        if DESC_COL in new_df.columns and DESC_COL != desc_col:
            rename[DESC_COL] = desc_col
        if CLASS_COL in new_df.columns and CLASS_COL != class_col:
            rename[CLASS_COL] = class_col
        if PO_COL in new_df.columns and PO_COL != po_col and po_col:
            rename[PO_COL] = po_col
        if rename:
            new_df = new_df.rename(columns=rename)
    else:
        desc_col = DESC_COL
        class_col = CLASS_COL
        po_col = PO_COL

    merged, updated_meta = append_to_master(taxonomy_key, new_df, desc_col, class_col, po_col)
    return {"ok": True, "total_rows": len(merged)}


@router.post("/classify/download")
async def classify_download_results(
    results_json: str = Form(...),
) -> Response:
    try:
        results = json.loads(results_json)
        if not isinstance(results, list):
            raise ValueError("results_json must be an array")
    except Exception as exc:
        raise HTTPException(400, f"Invalid results_json: {exc}")

    df = pd.DataFrame(results)
    buf = BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=classification_results.xlsx"},
    )
