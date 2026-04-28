"""Unit tests for the universal DMA `/upload-preview` endpoint.

The shared `FileUpload` React component (used by every DMA agent page —
GroupDuplicates, Lookup, Classify, MasterBuilder, DataEnrichment) calls
`POST /api/dma/upload-preview` immediately after the user picks a file,
and renders the response into the per-page preview table + column pickers.

The endpoint must:

  * accept .xlsx / .xls / .csv (matching the frontend `accept` attribute)
  * return `{columns, preview, row_count}` — the exact shape the React
    pages destructure into `fileData`
  * cap preview length so a 100k-row file doesn't blow up the JSON
    response (`PreviewTable` only renders the first handful anyway)
  * reject empty / malformed uploads with HTTP 400 and a useful detail
    string (the FileUpload component surfaces `err.response.data.detail`)

We test the route function directly with a constructed `UploadFile` —
this matches how `test_oracle_ebs_r12_connector.py` exercises its
handler. No DB, no network, no auth dance.
"""

from __future__ import annotations

import asyncio
from io import BytesIO

import pandas as pd
import pytest
from fastapi import HTTPException, UploadFile

from app.dma.routes.upload import upload_preview


def _csv_upload(text: str, name: str = "in.csv") -> UploadFile:
    return UploadFile(filename=name, file=BytesIO(text.encode("utf-8")))


def _xlsx_upload(df: pd.DataFrame, name: str = "in.xlsx") -> UploadFile:
    bio = BytesIO()
    df.to_excel(bio, index=False)
    bio.seek(0)
    return UploadFile(filename=name, file=bio)


def _run(coro):
    """The handler is async, but the project doesn't ship pytest-asyncio.
    Drive the coroutine through asyncio.run so tests stay plugin-agnostic."""
    return asyncio.run(coro)


# ── happy paths ──────────────────────────────────────────────────────────────


def test_csv_upload_returns_columns_preview_and_row_count():
    upload = _csv_upload("name,price\nfoo,10\nbar,20\nbaz,30\n")

    result = _run(upload_preview(file=upload))

    assert result["columns"] == ["name", "price"]
    assert result["row_count"] == 3
    # preview rows are dicts keyed by column name (PreviewTable does r[c])
    assert result["preview"] == [
        {"name": "foo", "price": "10"},
        {"name": "bar", "price": "20"},
        {"name": "baz", "price": "30"},
    ]


def test_xlsx_upload_returns_columns_preview_and_row_count():
    df = pd.DataFrame({"sku": ["A1", "B2"], "qty": [5, 7]})
    upload = _xlsx_upload(df)

    result = _run(upload_preview(file=upload))

    assert result["columns"] == ["sku", "qty"]
    assert result["row_count"] == 2
    assert len(result["preview"]) == 2
    assert result["preview"][0]["sku"] == "A1"


def test_preview_is_capped_but_row_count_reflects_full_file():
    """A large file should still show row_count for the whole dataset, but
    the preview must be truncated — the React PreviewTable only renders a
    handful of rows and we don't want a 50k-row JSON payload on every
    upload."""
    rows = "\n".join(f"row{i},{i}" for i in range(100))
    upload = _csv_upload(f"name,n\n{rows}\n")

    result = _run(upload_preview(file=upload))

    assert result["row_count"] == 100
    assert len(result["preview"]) <= 20  # cap is small; exact value is impl detail


def test_nan_values_serialize_as_empty_strings():
    """Pandas' NaN doesn't survive a JSON round-trip cleanly. The endpoint
    coerces missing cells to "" so PreviewTable's `r[c] ?? ""` doesn't see
    `null`/`NaN` strings in the rendered table."""
    upload = _csv_upload("a,b\n1,\n,2\n")

    result = _run(upload_preview(file=upload))

    assert result["row_count"] == 2
    # Both blanks become empty strings, not "nan" / None
    for row in result["preview"]:
        for v in row.values():
            assert v != "nan"
            assert v is not None


# ── error paths ──────────────────────────────────────────────────────────────


def test_empty_upload_returns_400():
    upload = UploadFile(filename="empty.csv", file=BytesIO(b""))

    with pytest.raises(HTTPException) as exc:
        _run(upload_preview(file=upload))

    assert exc.value.status_code == 400
    assert "empty" in exc.value.detail.lower()


def test_garbage_bytes_return_400_with_useful_detail():
    """`pd.read_csv` happily parses random binary as a 0-row, 1-column
    DataFrame with `Unnamed: 0` as the column name. Without an explicit
    "no data rows" check the user would see a broken-looking preview
    table and no error — they'd assume the upload worked and waste time
    debugging downstream. The endpoint catches that here.

    The frontend surfaces err.response.data.detail directly to the user,
    so the message needs to mention the format expectation."""
    upload = UploadFile(filename="bad.bin", file=BytesIO(b"\x00\x01\x02not a spreadsheet"))

    with pytest.raises(HTTPException) as exc:
        _run(upload_preview(file=upload))

    assert exc.value.status_code == 400
    detail = exc.value.detail.lower()
    assert "excel" in detail or "csv" in detail or "data rows" in detail


def test_header_only_csv_returns_400():
    """Edge case: a CSV with column headers but zero data rows is parsed
    cleanly by pandas, but no DMA flow can do anything with zero rows.
    Reject with the same "no data rows" detail."""
    upload = _csv_upload("col_a,col_b\n")

    with pytest.raises(HTTPException) as exc:
        _run(upload_preview(file=upload))

    assert exc.value.status_code == 400
    assert "data rows" in exc.value.detail.lower()


# ── route registration ───────────────────────────────────────────────────────


def test_route_is_registered_at_expected_path():
    """Catches accidental rename / unregistration. The frontend hard-codes
    `POST /api/dma/upload-preview` in `frontend/src/dma/api.js`."""
    from app.dma.routes import upload as upload_module

    paths = [r.path for r in upload_module.router.routes]
    assert "/upload-preview" in paths


def test_router_is_wired_into_main_app():
    """Defends against the original bug recurring: route file exists but
    is never `include_router`'d into the FastAPI app, so requests 404."""
    from app.main import app

    paths = {r.path for r in app.routes}
    assert "/api/dma/upload-preview" in paths
