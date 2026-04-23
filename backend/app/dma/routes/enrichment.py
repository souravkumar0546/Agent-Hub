from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response

from app.dma.services.enrichment_service import enrich_dataframe_async

router = APIRouter(tags=["enrichment"])


@router.post("/enrichment/enrich")
async def enrichment_enrich(
    file: UploadFile = File(...),
    cas_col: str = Form(...),
) -> dict:
    try:
        raw = await file.read()
        df = pd.read_excel(BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read Excel file: {exc}")

    if cas_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column not found: {cas_col}")

    enriched_df, summary = await enrich_dataframe_async(df, cas_col)

    rows = enriched_df.fillna("").to_dict(orient="records")
    return {
        "rows": rows,
        "columns": list(enriched_df.columns),
        "summary": summary,
    }


@router.post("/enrichment/download")
async def enrichment_download(
    file: UploadFile = File(...),
    cas_col: str = Form(...),
) -> Response:
    try:
        raw = await file.read()
        df = pd.read_excel(BytesIO(raw))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not read Excel file: {exc}")

    if cas_col not in df.columns:
        raise HTTPException(status_code=400, detail=f"Column not found: {cas_col}")

    enriched_df, _ = await enrich_dataframe_async(df, cas_col)

    out = BytesIO()
    enriched_df.to_excel(out, index=False, engine="openpyxl")

    return Response(
        content=out.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=enriched_data.xlsx"},
    )
