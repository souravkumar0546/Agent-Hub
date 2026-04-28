"""Universal file-preview endpoint for DMA agent pages.

The shared `FileUpload` React component (frontend/src/dma/components/FileUpload.jsx)
posts every newly-picked file to `POST /api/dma/upload-preview` as the very
first step in any DMA flow — Group Duplicates, Lookup, Classify, Master
Builder, and Data Enrichment all rely on it. The response feeds into the
column pickers and the small preview table the user sees before they kick
off the actual analysis, so this needs to be cheap and tolerant of the
file types the uploader's `accept=".xlsx,.xls,.csv"` filter lets through.

This module exists separately from the agent-specific route files (which
own their own analysis endpoints) because the preview is genuinely shared
— putting it on, say, classification.py would make the path lopsided
(`/classification/upload-preview` for the GroupDuplicates flow makes no
sense) and create an artificial coupling.
"""

from __future__ import annotations

from io import BytesIO

import pandas as pd
from fastapi import APIRouter, File, HTTPException, UploadFile

router = APIRouter(tags=["dma-upload"])

# Cap the preview rows we send back. PreviewTable renders into a fixed-
# height scrollable container and the user only ever needs a handful to
# pick the right columns; meanwhile some uploads are 50k+ rows, and
# shipping that whole table on every file pick would balloon the response
# and slow the UI down for no benefit. row_count below is still computed
# from the full DataFrame, so the "Classify All (N rows)" button shows
# the real total.
_PREVIEW_ROWS = 10


def _read_table_upload(raw: bytes) -> pd.DataFrame:
    """Decode an upload as Excel first, falling back to CSV.

    Mirrors the helper in `classification.py` so this universal preview
    accepts the same set of inputs as the per-agent endpoints. The order
    matters: pandas will happily mis-read a one-column .xlsx as CSV but
    not the other way around, so we try the stricter parser first.
    """
    bio = BytesIO(raw)
    try:
        return pd.read_excel(bio)
    except Exception:
        bio.seek(0)
        return pd.read_csv(bio)


@router.post("/upload-preview")
async def upload_preview(file: UploadFile = File(...)) -> dict:
    """Return columns, a small head() preview, and the full row count.

    Response shape is dictated by `frontend/src/dma/api.js::uploadPreview`
    and the `fileData` consumers in the per-agent pages — `columns` feeds
    the SingleColumnPicker, `preview` feeds PreviewTable (which dict-
    indexes each row by column name), and `row_count` is shown on the
    primary action button.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        df = _read_table_upload(raw)
    except Exception as exc:
        # The frontend's FileUpload surfaces err.response.data.detail
        # directly, so the message has to be human-readable and mention
        # the formats we accept — otherwise users see a useless "400 Bad
        # Request" toast and don't know what to fix.
        raise HTTPException(
            status_code=400,
            detail=f"Could not read file as Excel or CSV: {exc}",
        )

    # `pd.read_csv` is permissive enough to swallow non-spreadsheet bytes
    # (PDFs, images, random binary) and hand back an empty single-column
    # DataFrame. None of the DMA agents can do anything with zero rows,
    # so reject that here with a hint at the likely cause — otherwise
    # the user sees a preview table with `Unnamed: 0` as the only column
    # and no rows, which is more confusing than a 400.
    if len(df) == 0:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not read any data rows. The file may not be a valid "
                "Excel or CSV spreadsheet, or it may be header-only."
            ),
        )

    # NaN, datetimes, and pd.NA don't all survive a JSON round-trip
    # cleanly — fillna("") + astype(str) gives PreviewTable predictable
    # strings to render and avoids the "nan" cells we'd otherwise see.
    head = df.head(_PREVIEW_ROWS).fillna("").astype(str)
    return {
        "columns": list(df.columns),
        "preview": head.to_dict(orient="records"),
        "row_count": int(len(df)),
    }
