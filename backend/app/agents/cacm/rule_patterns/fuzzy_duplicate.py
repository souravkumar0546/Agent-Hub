"""fuzzy_duplicate — cluster near-duplicate rows by text similarity.

Builds a TF-IDF representation over the concatenated text of `compare_columns`
and groups rows whose pairwise cosine similarity exceeds `threshold`. Uses
sklearn (already a project dependency via the DMA module).

Each cluster of >=2 rows produces one ExceptionRecord listing the duplicate IDs.
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.agents.cacm.types import ExceptionRecord, RuleContext


def fuzzy_duplicate(ctx: RuleContext, params: dict[str, Any]) -> list[ExceptionRecord]:
    table = params["table"]
    id_col = params["id_column"]
    cmp_cols = params["compare_columns"]
    threshold = float(params["threshold"])
    risk = params["risk"]
    reason_template = params["reason_template"]

    df = ctx.tables[table].reset_index(drop=True)
    if df.empty:
        return []

    # Concatenate compare columns to a single text per row, lowercased + spaces normalised.
    # Use character n-grams (char_wb) so small typos / whitespace differences ("250ml" vs
    # "250 ml") still match — token-based TF-IDF treats those as completely different words.
    blob = df[cmp_cols].astype(str).agg(" ".join, axis=1).str.lower()
    vec = TfidfVectorizer(min_df=1, analyzer="char_wb", ngram_range=(2, 4)).fit_transform(blob)
    sim = cosine_similarity(vec)

    # Union-find clustering across pairs above threshold.
    parent = list(range(len(df)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    n = len(df)
    for i in range(n):
        for j in range(i + 1, n):
            if sim[i, j] >= threshold:
                union(i, j)

    clusters: dict[int, list[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    excs: list[ExceptionRecord] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        ids = [str(df.loc[i, id_col]) for i in members]
        # Average similarity score within the cluster.
        scores = [sim[i, j] for i in members for j in members if i < j]
        avg = float(sum(scores) / len(scores)) if scores else 1.0
        excs.append(ExceptionRecord(
            exception_no="",
            risk=risk if isinstance(risk, str) else "Medium",
            reason=reason_template.format(ids=", ".join(ids), score=avg),
            value=float(len(members)),
            fields={"ids": ids, "size": len(members), "avg_score": round(avg, 3)},
        ))
    return excs
