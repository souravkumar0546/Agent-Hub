# Data Classifier

Takes a spreadsheet of new records and classifies each one against an organisational master, per taxonomy. Useful whenever a system spits out free-text descriptions that need a category code (material class, cost category, spare-part type, etc.).

## Workflow

1. Open the **Data Classifier** card from the hub.
2. Pick the **taxonomy** you want to classify against. Available taxonomies in this release:
   - `ZSC1` — Consumables (level 1)
   - `ZSC2` — Consumables (level 2, more granular)
   - `ZRDM` — Raw Materials
   - `ZCAP` — Capex
   - `ERSA` — Spares
3. Either enter a **single description** (quick test) or upload an **Excel batch**.
   - For a batch: upload an `.xlsx` file, then pick the column containing the free-text description. Optionally pick the purchase-order column if you want to keep PO context in the output.
4. Set the similarity threshold if you want stricter matching (default 0.65).
5. Click **Run**. The pipeline:
   - Loads the persisted master for the taxonomy
   - Builds a TF-IDF index over the master's descriptions
   - For each input row, finds the nearest master record using blocking + cosine similarity
   - Confirms or overrides the match with the AI classifier
6. Review the preview table. Each row shows the suggested class, the confidence, and the master record that drove the decision.
7. Download the results as Excel, or **Add to master** to persist selected rows as new master entries — they'll be available to future classify runs.

## When to use which taxonomy

| If the records are | Pick |
|---|---|
| Lab reagents, PPE, cleaning chemicals, solvents | `ZSC1` or `ZSC2` |
| Active pharmaceutical ingredients, excipients | `ZRDM` |
| Equipment, facility projects, IT hardware purchases | `ZCAP` |
| Maintenance spares (bearings, seals, filters) | `ERSA` |

If the taxonomy you need isn't in the list, contact an org admin — new taxonomies are added at the platform level.

## Tips

- Bigger master → better matching. If the taxonomy's master is sparse, use **Master Builder** first to clean and seed it.
- Keep description columns clean — remove internal codes, leading/trailing whitespace, and irrelevant qualifiers before classifying for best results.
