from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.dma.services.dedup_group_service import analyze_group_duplicates, build_duplicate_report_colored_xlsx


router = APIRouter(tags=["group-duplicates"])


@router.post("/group-duplicates/analyze")
async def group_duplicates_analyze(
    file: UploadFile = File(...),
    threshold: float = Form(0.85),
    selected_cols: str = Form(...),
    identifier_col: str = Form(...),
    apply_ai_variant_filter: bool = Form(True),
) -> dict:
    try:
        raw = await file.read()
        df = pd.read_excel(BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read excel file: {exc}")

    columns = [c.strip() for c in selected_cols.split(",") if c.strip()]
    if not columns:
        raise HTTPException(status_code=400, detail="selected_cols is required")
    for c in columns:
        if c not in df.columns:
            raise HTTPException(status_code=400, detail=f"Column not found: {c}")
    if identifier_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Identifier column not found: {identifier_col}")

    rows = await analyze_group_duplicates(
        df=df,
        selected_cols=columns,
        identifier_col=identifier_col,
        threshold=float(threshold),
        apply_ai_variant_filter=bool(apply_ai_variant_filter),
    )
    return {"rows": rows, "count": len(rows), "columns": list(df.columns)}


@router.post("/group-duplicates/colored-xlsx")
async def group_duplicates_colored_xlsx(rows_json: str = Form(...)) -> Response:
    try:
        rows = json.loads(rows_json)
        if not isinstance(rows, list) or not rows:
            raise HTTPException(status_code=400, detail="rows_json must be a non-empty JSON array")
        data = build_duplicate_report_colored_xlsx(rows)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not build XLSX: {exc}")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=duplicate_report_colored.xlsx"},
    )

