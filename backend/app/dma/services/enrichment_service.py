"""
Data Enrichment Service — BLDPharm CAS-based taxonomy lookup.

For each row with a CAS Number, fetches the BLDPharm product page and extracts
the breadcrumb classification. Single request per CAS (no retries).

Uses asyncio + httpx so it doesn't block the FastAPI event loop, allowing
other agents to run concurrently.
"""
from __future__ import annotations

import asyncio
import re
from typing import Optional

import httpx
import pandas as pd
from bs4 import BeautifulSoup

# ------------ Config ------------
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}
RATE_LIMIT_SECONDS = 0.8
TIMEOUT = 20
BLD_BASE = "https://www.bldpharm.com"


def _parse_breadcrumbs(html: str) -> Optional[str]:
    """Extract breadcrumb taxonomy from a BLDPharm product page."""
    soup = BeautifulSoup(html, "html.parser")
    crumb_container = soup.select_one(".breadcrumb, .crumb, .breadcrumbs")
    crumbs: list[str] = []

    if crumb_container:
        for node in crumb_container.select("a, span, li"):
            txt = (node.get_text(" ", strip=True) or "").strip()
            if txt:
                crumbs.append(txt)
    else:
        # Regex fallback: look for "Products > ..."
        text = soup.get_text(" ", strip=True)
        m = re.search(r"(Products\s*>.*)", text)
        if m:
            segment = m.group(1)
            segment = re.split(r"(Size|Price|Documents|SDS|Quantity)\b", segment)[0]
            return " ".join(segment.split())

    crumbs = [c for c in crumbs if c and c not in {"Home", ""}]
    return " > ".join(crumbs) if crumbs else None


async def _fetch_one(
    client: httpx.AsyncClient, cas: str
) -> tuple[str, str, str]:
    """
    Single CAS lookup: construct URL directly, fetch page, parse breadcrumbs.
    One HTTP request per CAS — no separate URL-check step.
    Returns (classification, source, status).
    """
    cas = (cas or "").strip()
    if not cas:
        return "No CAS number.", "Unmapped | (no CAS)", "Unmapped"

    # Clean CAS: keep only digits and hyphens (handles stray spaces, letters, etc.)
    cas_clean = re.sub(r"[^0-9\-]", "", cas).strip("-")
    if not cas_clean:
        return "No valid CAS number.", "Unmapped | (no CAS)", "Unmapped"

    url = f"{BLD_BASE}/products/{cas_clean}.html"
    try:
        resp = await client.get(url)
        if resp.status_code != 200:
            return "Not found on BLDPharm.", "Unmapped | (no evidence)", "Unmapped"
    except httpx.HTTPError:
        return "Not found on BLDPharm.", "Unmapped | (no evidence)", "Unmapped"

    # Rate-limit: yield control for a bit to be polite
    await asyncio.sleep(RATE_LIMIT_SECONDS)

    klass = _parse_breadcrumbs(resp.text)
    if klass:
        return klass, f"BLDPharm | {url}", "BLDPharm"
    return "Not found on BLDPharm.", "Unmapped | (no evidence)", "Unmapped"


async def enrich_dataframe_async(
    df: pd.DataFrame,
    cas_col: str,
) -> tuple[pd.DataFrame, dict]:
    """
    Enrich a DataFrame by looking up each CAS number on BLDPharm.
    Async — does not block the FastAPI event loop.
    Returns (enriched_df, summary_dict).
    """
    results_search: list[str] = []
    results_source: list[str] = []
    status_labels: list[str] = []

    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        for _, row in df.iterrows():
            cas = str(row.get(cas_col, "") or "").strip()
            try:
                klass, source, status = await _fetch_one(client, cas)
            except Exception as e:
                klass = f"ERROR: {e}"
                source = "Processing error"
                status = "ERROR"
            results_search.append(klass)
            results_source.append(source)
            status_labels.append(status)

    enriched = df.copy()
    enriched["Search Result"] = results_search
    enriched["Source / Evidence"] = results_source

    mapped = sum(1 for s in status_labels if s == "BLDPharm")
    unmapped = sum(1 for s in status_labels if s == "Unmapped")
    errors = sum(1 for s in status_labels if s == "ERROR")

    summary = {
        "total_rows": len(df),
        "mapped": mapped,
        "unmapped": unmapped,
        "errors": errors,
    }
    return enriched, summary
