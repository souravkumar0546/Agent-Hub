from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def _corpus_tfidf_sim(query: str, corpus: list[str], row_idx: int) -> float:
    if not query.strip():
        return 0.0
    try:
        all_texts = corpus + [query]
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True)
        tfidf = vec.fit_transform(all_texts)
        return float(cosine_similarity(tfidf[-1:], tfidf[row_idx:row_idx + 1])[0][0])
    except Exception:
        return 0.0


def _token_containment(query: str, reference: str) -> float:
    q = query.lower().strip()
    r = reference.lower().strip()
    if not q or not r:
        return 0.0
    q_tokens = q.split()
    if not q_tokens:
        return 0.0
    matched = sum(1 for t in q_tokens if t in r)
    containment = matched / len(q_tokens)
    matched_chars = sum(len(t) for t in q_tokens if t in r)
    r_alpha = "".join(c for c in r if c.isalnum())
    coverage = matched_chars / max(len(r_alpha), 1)
    return containment * 0.7 + min(coverage, 1.0) * 0.3


def _tfidf_search(query: str, corpus: list[str], top_n: int = 5, threshold: float = 0.5) -> list[tuple[int, float]]:
    if not corpus or not query.strip():
        return []
    all_texts = corpus + [query]
    try:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), lowercase=True)
        tfidf = vec.fit_transform(all_texts)
        sims = cosine_similarity(tfidf[-1:], tfidf[:-1]).flatten()
        top_indices = np.argsort(sims)[::-1][:top_n]
        return [(int(idx), float(sims[idx])) for idx in top_indices if sims[idx] >= threshold]
    except Exception:
        return []


def _build_corpus(df: pd.DataFrame, columns: list[str]) -> list[str]:
    corpus = []
    for _, row in df.iterrows():
        parts = []
        for col in columns:
            val = row.get(col, "")
            if pd.notna(val) and str(val).strip():
                parts.append(str(val).strip())
        corpus.append(" | ".join(parts))
    return corpus


def _build_column_corpora(df: pd.DataFrame, columns: list[str]) -> dict[str, list[str]]:
    corpora = {}
    for col in columns:
        corpora[col] = [str(val).strip() if pd.notna(val) and str(val).strip() else "" for val in df[col]]
    return corpora


def _keyword_match_indices(filled_values: dict[str, str], corpus: list[str]) -> list[int]:
    tokens: list[str] = []
    for val in filled_values.values():
        val = (val or "").strip().lower()
        if not val:
            continue
        for tok in val.split():
            if tok and tok not in tokens:
                tokens.append(tok)
    if not tokens:
        return []
    matches: list[int] = []
    for i, text in enumerate(corpus):
        t = (text or "").lower()
        if all(tok in t for tok in tokens):
            matches.append(i)
    return matches


def _column_scores(input_values: dict[str, str], col_corpora: dict[str, list[str]], idx: int, columns: list[str]) -> dict[str, float]:
    scores = {}
    for col in columns:
        input_val = (input_values.get(col, "") or "").strip()
        corpus = col_corpora[col]
        ref_val = corpus[idx] if idx < len(corpus) else ""
        if not ref_val or ref_val.lower() == "nan":
            scores[col] = None
        elif not input_val:
            scores[col] = None
        else:
            tfidf = _corpus_tfidf_sim(input_val, corpus, idx)
            contain = _token_containment(input_val, ref_val)
            scores[col] = max(tfidf, contain)
    return scores


def _weighted_overall(per_col: dict[str, float | None], columns: list[str]) -> float:
    if not columns:
        return 0.0
    primary = columns[0]
    secondary = columns[1:]
    primary_score = per_col.get(primary)
    if primary_score is None:
        return 0.0
    if not secondary:
        return primary_score
    sec_scores = [per_col[c] for c in secondary if per_col.get(c) is not None]
    if not sec_scores:
        return primary_score
    sec_avg = sum(sec_scores) / len(sec_scores)
    return primary_score * 0.6 + sec_avg * 0.4


def analyze_lookup(
    df_ref: pd.DataFrame,
    selected_cols: list[str],
    input_values: dict[str, str],
    threshold: float,
    top_n: int,
) -> dict:
    filled_values = {k: v for k, v in input_values.items() if (v or "").strip()}
    if not filled_values:
        return {"error": "Please fill in at least one field."}

    primary_col = selected_cols[0]
    col_corpora = _build_column_corpora(df_ref, selected_cols)
    combined_corpus = _build_corpus(df_ref, selected_cols)
    primary_query = (input_values.get(primary_col, "") or "").strip()

    exact_indices = []
    if primary_query:
        for i in range(len(df_ref)):
            all_match = True
            for col in selected_cols:
                inp = (input_values.get(col, "") or "").strip().lower()
                ref = (col_corpora[col][i] or "").strip().lower()
                if not inp:
                    continue
                if inp != ref:
                    all_match = False
                    break
            if all_match:
                exact_indices.append(i)

    candidate_threshold = threshold * 0.7
    if not primary_query:
        candidates = []
    else:
        candidates = list(_tfidf_search(primary_query, col_corpora[primary_col], top_n * 3, candidate_threshold))

    candidates = [c for c in candidates if c[0] not in set(exact_indices)]
    keyword_indices = _keyword_match_indices(filled_values, combined_corpus)
    existing_indices = {idx for idx, _ in candidates}
    for idx in keyword_indices:
        if idx in exact_indices or idx in existing_indices:
            continue
        candidates.append((idx, 0.97))

    scored_results = []
    for idx, _ in candidates:
        per_col = _column_scores(input_values, col_corpora, idx, selected_cols)
        overall = _weighted_overall(per_col, selected_cols)
        scored_results.append((idx, per_col, overall))
    scored_results.sort(key=lambda x: -x[2])
    scored_results = scored_results[:top_n]

    verdict = "NO MATCH"
    if scored_results:
        top_overall = scored_results[0][2]
        top_per_col = scored_results[0][1]
        top_primary = top_per_col.get(primary_col, 0) or 0
        secondary_cols = selected_cols[1:]
        sec_scores = [top_per_col.get(c) for c in secondary_cols if top_per_col.get(c) is not None]
        if top_overall >= 0.95:
            verdict = "VERY LIKELY DUPLICATE"
        elif top_overall >= threshold:
            verdict = "POSSIBLE DUPLICATE"
        elif top_primary >= threshold and sec_scores and all(s < 0.50 for s in sec_scores):
            verdict = f"{primary_col} MATCHES, but other columns DIFFER"
        else:
            verdict = "LOW SIMILARITY MATCHES"
    elif exact_indices:
        verdict = "EXACT MATCH"

    exact_rows = df_ref.iloc[exact_indices].fillna("").to_dict(orient="records") if exact_indices else []
    similar_rows = []
    for idx, per_col, overall in scored_results:
        ref_data = df_ref.iloc[idx].fillna("").to_dict()
        similar_rows.append(
            {
                "overall": round(overall * 100, 2),
                "per_column": {c: (None if per_col.get(c) is None else round(per_col[c] * 100, 2)) for c in selected_cols},
                "record": {k: str(v) for k, v in ref_data.items()},
            }
        )

    return {
        "verdict": verdict,
        "exact_match_count": len(exact_rows),
        "exact_matches": [{k: str(v) for k, v in row.items()} for row in exact_rows],
        "similar_matches": similar_rows,
    }

