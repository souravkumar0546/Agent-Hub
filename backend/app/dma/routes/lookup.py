from __future__ import annotations

import json
from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.dma.services.lookup_service import analyze_lookup


router = APIRouter(tags=["lookup"])


@router.post("/lookup/analyze")
async def lookup_analyze(
    file: UploadFile = File(...),
    threshold: float = Form(0.80),
    top_n: int = Form(5),
    selected_cols: str = Form(...),
    input_values_json: str = Form(...),
) -> dict:
    try:
        raw = await file.read()
        df_ref = pd.read_excel(BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read excel file: {exc}")

    columns = [c.strip() for c in selected_cols.split(",") if c.strip()]
    if not columns:
        raise HTTPException(status_code=400, detail="selected_cols is required")
    for c in columns:
        if c not in df_ref.columns:
            raise HTTPException(status_code=400, detail=f"Column not found: {c}")

    try:
        input_values = json.loads(input_values_json)
        if not isinstance(input_values, dict):
            raise ValueError("input_values_json must be object")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid input_values_json: {exc}")

    return analyze_lookup(
        df_ref=df_ref,
        selected_cols=columns,
        input_values={str(k): str(v) for k, v in input_values.items()},
        threshold=float(threshold),
        top_n=int(top_n),
    )

