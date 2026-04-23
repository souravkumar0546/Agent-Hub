# Investigation (RCA) Agent

The Investigation agent drafts GMP investigation reports in the FORM-GMP-QA-0504 format. It handles deviation intake, root-cause analysis, and CAPA drafting. It's chat-based and multi-turn — you describe the deviation (optionally with supporting documents) and the agent fills a structured template as you go.

## Dashboard

Clicking the **RCA / Investigation Agent** card takes you to a dashboard, not straight into a chat. The dashboard shows:

- Total investigations, this week, this month (with change vs the previous period)
- Average coverage, completion rate, average duration, follow-up rate
- A line chart of investigations over the last 30 days
- A coverage histogram and phase breakdown donut
- A weekly success-rate chart and the top referenced SOPs
- A filterable table of recent investigations

Click any row in the table to jump into that investigation's conversation.

## Starting a new investigation

1. Click **+ New Investigation** on the dashboard header.
2. You land in the chat workspace. The left pane is the conversation; the right pane is a live preview of the FORM-GMP-QA-0504 draft.
3. Describe the deviation in the message box. Include PR number, department, initiator, timeline, affected system, and anything else you would put in a written report.
4. Optionally attach supporting documents. Accepted types: `.pdf`, `.doc`, `.docx`, `.txt`, `.csv`, `.log`. Up to 10 MB per file, multiple files at once.
5. Hit **Send** or ⌘/Ctrl + Enter. The message clears immediately; the agent is working. Runs typically take 60–80 seconds on GPT-5.3.
6. When the reply lands, the right-pane draft updates with filled sections highlighted in accent colour.

## Coverage % and phase

The header shows two pills that update after every turn:

- **Coverage %** — fraction of required + conditional template fields that are filled or in needs-review.
- **Phase** — the run's lifecycle stage, derived from coverage:
  - `intake` (< 15 %) — early information capture
  - `gap_analysis` (15–40 %) — identifying what's missing
  - `targeted_qa` (40–70 %) — filling specific gaps
  - `drafting` (70–90 %) — writing formal prose
  - `review` (≥ 90 %) — ready for human review

## Editing fields directly

Click any field in the right-pane preview to edit it inline. Your edit is saved as its own run (chained to the current one) so the history records who changed what. The draft immediately re-renders with your value, status flipped to `filled`.

User edits are never overwritten by the AI on subsequent turns unless you explicitly ask it to correct a field.

## Follow-up turns

Every message you send continues the same investigation. Backend-side, each turn creates a new `AgentRun` with `parent_run_id` pointing to the previous one. The conversation panel shows every turn, and the history strip across the top lets you jump back to any earlier state.

Use **New Investigation** in the header to start a fresh chain.

## Downloading the Word report

Once the draft has content, the **Download Report (.docx)** button in the header becomes active. Clicking it generates a FORM-GMP-QA-0504 Word document from the current run's session state, with every section rendered into the standard layout (tables, signature block, abbreviations). The filename includes the document reference number if one is set.

## SOP notes

If the agent detects compliance issues — missing justification for a short historical-check window, "human error" called out without systemic analysis, a Major/Critical deviation with missing impact sections — it appends one or more `SOP Note:` lines to its reply. These are plain advisories, not blockers; the report still exports.
