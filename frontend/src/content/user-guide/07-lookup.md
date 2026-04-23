# Lookup Agent

Answers the "is this a new thing, or does it already exist?" question. Given a reference dataset plus a set of new candidate values, the Lookup Agent scores each candidate against the reference and returns a weighted verdict per column plus an overall call.

## When to use it

- You've received a vendor list and want to know which vendors are already in the master
- Engineering submitted a parts request — check whether each item already exists in the spares master before raising a purchase
- Before creating a new material code, verify that nothing similar already exists

## Workflow

1. Open **Lookup Agent** from the hub.
2. Upload the **reference** spreadsheet — the "known good" master you want to compare against.
3. Pick the columns on the reference you want to match on (e.g. Description, Supplier Name, CAS Number).
4. Enter the **candidate values** as rows in the input grid. Each row = one candidate to check.
5. Set the similarity threshold and the number of top matches to return per candidate (default 5).
6. Click **Analyze**.

## Reading the verdict

For each candidate, the agent returns up to N top matches from the reference, ordered by overall similarity. Each match has:

- **Per-column similarity score** — how close the candidate is to the match on that specific column
- **Weighted overall score** — combined score across all selected columns
- **Verdict** — `EXACT MATCH`, `VERY LIKELY`, `POTENTIAL MATCH`, or `NO MATCH`

If the top match is `EXACT MATCH` or `VERY LIKELY`, treat the candidate as already-existing. `POTENTIAL MATCH` needs human review. `NO MATCH` confirms the candidate is genuinely new.

## Tips

- The more columns you select, the more discriminating the verdict — but each column contributes equally unless you change weights.
- Keep the reference fresh. If you find a duplicate during lookup, add the candidate to the master so the next lookup doesn't surface it.
