# Duplicate Groups (Group Duplicates)

Finds duplicate and near-duplicate records in a spreadsheet using multi-column similarity plus AI variant filtering. Use it when material masters, vendor masters, or any other reference data has drifted and you need to identify the clusters that should be merged.

## How it works

1. Text normalisation and TF-IDF vectorisation per column
2. Pairwise cosine similarity with a primary-column pre-filter for speed
3. Grouping into clusters with verdicts — **EXACT MATCH**, **VERY LIKELY**, **POTENTIAL**
4. AI variant validation pass — the LLM removes pairs that are same product, different SKU/size/qty (so "500 mL" and "1 L" of the same reagent aren't flagged as duplicates)
5. Colored Excel export, each cluster gets a distinct block colour

## Workflow

1. Open **Group Duplicates** from the hub.
2. Upload your `.xlsx`.
3. Pick an **identifier column** (e.g. Material Code, Vendor ID) — this is what becomes the row key in the output.
4. Pick **one or more comparison columns** (e.g. Description, Supplier Name). The agent computes similarity across every selected column and combines scores.
5. Set the similarity threshold (default 0.85; higher means stricter matching, fewer groups).
6. Toggle AI variant filtering on or off. Leave it **on** unless you're deliberately looking for pack-size variants too.
7. Click **Analyze**. Progress steps are shown in the UI — normalising → similarity → grouping → AI filter → report.
8. Review the grouped output. Each block is a cluster of likely duplicates.
9. Click **Download Colored XLSX** to save the colour-coded report for manual review.

## Reading the output

- **Block ID** — identifies a cluster. All rows with the same block ID are potential duplicates of each other.
- **Verdict** per row — how confident the system is:
  - `EXACT MATCH` — normalised text is identical
  - `VERY LIKELY` — high similarity after normalisation
  - `POTENTIAL` — borderline; human review recommended
- **Block colour** in the exported Excel — alternating pairs so you can visually scan clusters.

Rows that have no duplicates aren't in the output at all — the report is only the pairs the agent found.
