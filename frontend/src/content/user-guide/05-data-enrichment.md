# Data Enrichment

Fills in missing attributes on a spreadsheet by looking up each row in external reference sources. Today the pipeline enriches from **CAS numbers** (the Chemical Abstracts Service registry) to pull synonyms, molecular formula, molecular weight, and related metadata.

## Workflow

1. Open **Data Enrichment** from the hub.
2. Upload a `.xlsx` file containing a CAS-number column.
3. Pick the CAS column from the dropdown. The agent inspects the first few rows to help you spot the right one.
4. Click **Enrich**. The agent looks up each CAS number in the reference sources and adds extra columns to the dataset:
   - Preferred name
   - Synonyms
   - Molecular formula
   - Molecular weight
   - External URLs (PubChem, ChemSpider, etc.)
5. Preview the enriched rows. Rows that couldn't be resolved are flagged.
6. Download the enriched Excel.

## Notes & limits

- Rate-limited by the upstream reference source. Large files (thousands of rows) can take several minutes.
- Empty or malformed CAS values are skipped, not errored — they come through with blank enrichment columns.
- Original columns are preserved in order; enriched columns are appended to the right.

## Future sources

The pipeline is designed to accept additional reference sources (supplier catalogues, internal databases) as they're added to the platform. If you need a lookup your CAS number can't provide, raise it with an org admin.
