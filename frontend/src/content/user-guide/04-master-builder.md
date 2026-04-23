# Master Builder

Master Builder cleans up an existing, messy master file and persists it as the authoritative master for a taxonomy. Use it when your source-of-truth master has inconsistent classifications, typos, and variant descriptions that need harmonising.

## Purpose

- Take an input master that's "close but not clean"
- Detect inconsistent classifications (same description → different class, or similar descriptions classified differently)
- Propose AI-driven corrections
- Review and accept
- Persist the cleaned master on the server, keyed by taxonomy, so Data Classifier and others can read from it

## Workflow

1. Open **Master Builder** from the hub.
2. Upload the master spreadsheet (`.xlsx`).
3. Pick the **description column** and the **class column**. Optionally pick columns for purchase order and material status so they carry through to the output.
4. Pick the target taxonomy key (`ZSC1`, `ZSC2`, `ZRDM`, `ZCAP`, `ERSA`).
5. Adjust the similarity threshold and AI batch size if needed (defaults are usually fine).
6. Click **Fix Master**. The job can take several minutes for large files — progress is shown step-by-step.
7. The result is a review table. Each problematic row shows the current class, the suggested class, and the reasoning.
8. Click **Add to Master** to persist the cleaned master. Existing entries for that taxonomy are replaced.

## Where masters are stored

Masters are persisted on the platform as `dma_master/<taxonomy_key>/master.xlsx` plus a small metadata file. Use **List Masters** to see which taxonomies have been seeded. Download any master as `.xlsx` for audit or backup.

## Which agents consume the master?

- **Data Classifier** — uses the master to categorise new records.
- **Lookup Agent** — uses it as the reference dataset for new-vs-reference checks.

When you rebuild a master, those agents immediately see the new data — no restart needed.
