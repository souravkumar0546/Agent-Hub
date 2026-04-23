from __future__ import annotations

import json
import uuid
from io import BytesIO
from typing import Optional

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response

from app.dma.services.classification_service import (
    build_download_bytes,
    classify_new_material,
    fix_master_data,
    get_taxonomy,
    get_all_taxonomies,
    set_taxonomy,
)

router = APIRouter(tags=["classification"])

# In-memory store for fixed master data so the frontend doesn't need to
# resend thousands of rows on every classify-new / download call.
_master_store: dict[str, dict] = {}


def _read_table_upload(raw: bytes) -> pd.DataFrame:
    bio = BytesIO(raw)
    try:
        return pd.read_excel(bio)
    except Exception:
        bio.seek(0)
        return pd.read_csv(bio)


@router.post("/classification/fix-master")
async def classification_fix_master(
    file: UploadFile = File(...),
    desc_col: str = Form(...),
    class_col: str = Form(...),
    po_col: str = Form(""),
    status_col: str = Form(""),
    sim_threshold: float = Form(0.65),
    ai_batch_size: int = Form(5),
    taxonomy_key: str = Form("ZSC1"),
) -> dict:
    try:
        df = _read_table_upload(await file.read())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read excel file: {exc}")

    if desc_col not in df.columns or class_col not in df.columns:
        raise HTTPException(status_code=400, detail="Invalid desc/class column")
    po = po_col if po_col and po_col in df.columns else None
    status = status_col if status_col and status_col in df.columns else None

    # Switch taxonomy before running
    set_taxonomy({"taxonomy_key": taxonomy_key})
    fixed_df, summary = await fix_master_data(df, desc_col, class_col, po, status, float(sim_threshold), int(ai_batch_size))
    changed = summary.get("changed_row_indices", [])
    rows = fixed_df.fillna("").astype(str).to_dict(orient="records")
    columns = list(fixed_df.columns)

    # Store on server so classify-new and download don't need the full payload
    master_id = uuid.uuid4().hex[:12]
    new_col = summary.get("new_col", "New Classification")
    _master_store[master_id] = {"rows": rows, "columns": columns, "df": fixed_df, "new_col": new_col}

    return {
        "summary": summary,
        "rows": rows,
        "columns": columns,
        "changed_row_indices": changed,
        "master_id": master_id,
    }


@router.post("/classification/master-add-row")
async def classification_master_add_row(
    master_id: str = Form(...),
    row_json: str = Form(...),
) -> dict:
    """Append a newly classified row to the server-side master store."""
    if master_id not in _master_store:
        raise HTTPException(status_code=404, detail="master_id not found")
    try:
        row = json.loads(row_json)
        if not isinstance(row, dict):
            raise ValueError("row_json must be an object")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid row_json: {exc}")
    _master_store[master_id]["rows"].append(row)
    # Also update the DataFrame used by download
    _master_store[master_id]["df"] = pd.DataFrame(_master_store[master_id]["rows"])
    return {"ok": True, "total_rows": len(_master_store[master_id]["rows"])}


@router.post("/classification/classify-new")
async def classification_classify_new(
    file: Optional[UploadFile] = File(None),
    desc_col: str = Form(...),
    class_col: str = Form(...),
    input_values_json: str = Form(...),
    sim_threshold: float = Form(0.65),
    master_id: str = Form(""),
    master_rows_json: str = Form(""),
) -> dict:
    """Use `master_id` (server-side cached), `master_rows_json`, or `file` — in that priority order."""
    try:
        if master_id and master_id in _master_store:
            df = pd.DataFrame(_master_store[master_id]["rows"])
        elif master_rows_json and master_rows_json.strip():
            df = pd.DataFrame(json.loads(master_rows_json))
        else:
            if file is None:
                raise HTTPException(status_code=400, detail="Upload a file or pass master_id")
            df = _read_table_upload(await file.read())
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not load master data: {exc}")
    if desc_col not in df.columns or class_col not in df.columns:
        raise HTTPException(status_code=400, detail="Invalid desc/class column")
    try:
        inputs = json.loads(input_values_json)
        if not isinstance(inputs, dict):
            raise ValueError("input_values_json must be object")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid input_values_json: {exc}")
    return await classify_new_material(df, desc_col, class_col, {str(k): str(v) for k, v in inputs.items()}, float(sim_threshold))



@router.post("/classification/download-highlighted")
async def classification_download_highlighted(
    class_col: str = Form(...),
    master_id: str = Form(""),
):
    """Yellow-highlight rows where old classification differs from New Classification."""
    if not master_id or master_id not in _master_store:
        raise HTTPException(status_code=400, detail="Provide a valid master_id")
    store = _master_store[master_id]
    df = store["df"]
    new_col = store.get("new_col", "New Classification")
    if class_col not in df.columns:
        raise HTTPException(status_code=400, detail="Invalid class column")
    data = build_download_bytes(df, class_col, new_col)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=master_data_highlighted.xlsx"},
    )


@router.get("/classification/taxonomy-options")
async def classification_taxonomy_options() -> list:
    """Return list of available material type taxonomies for dropdown."""
    return get_all_taxonomies()


@router.get("/classification/taxonomy")
async def classification_get_taxonomy() -> dict:
    """Return current taxonomy: categories (with definitions/examples), override rules."""
    return get_taxonomy()


@router.put("/classification/taxonomy")
async def classification_update_taxonomy(request: Request) -> dict:
    """Update taxonomy config. Body JSON: {categories, disambiguation_rules, override_rules}."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}")
    return set_taxonomy(body)

