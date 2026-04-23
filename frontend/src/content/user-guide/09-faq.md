# FAQ

## What does "Coverage %" mean on the Investigation dashboard?

It's the fraction of required + conditional template fields on FORM-GMP-QA-0504 that are filled (or in "needs review"). Partial fields count as half. Optional sections (fishbone, pareto, etc.) don't lower coverage when empty — they only count if the user or agent added them.

Coverage drives the phase pill: `< 15 %` = intake, `15–40 %` = gap analysis, `40–70 %` = targeted Q&A, `70–90 %` = drafting, `≥ 90 %` = review.

## Why does my investigation say "drafting" when it looks almost done?

Because one or more required fields is still empty. Common culprits: `investigation_team`, `sequence_of_events`, `document_ref_number`. Click the empty fields in the live template preview and fill them in — phase flips to `review` at 90 %.

## How does multi-turn work internally?

Each turn is stored as its own `AgentRun` row, chained by `parent_run_id`. When you send a follow-up message, the prior run's session state is loaded, the new message is processed, and a new run is written. That's why the history strip across the chat shows every turn, including inline field edits (which also create runs, with `duration_ms=0` and an `edit` badge).

"Investigations" in metrics = unique root runs (the ones with `parent_run_id = null`). Everything below them counts as turns.

## Can I edit a field the AI filled?

Yes — click the field in the right-pane preview and type. The edit is saved as a new run and tagged `last_edited_by = user`. The AI will not overwrite user-edited fields unless you specifically ask it to correct that field on a subsequent turn.

## Where do I find the audit log?

Org admins see **Audit Log** in the sidebar under ADMIN. It lists every `agent.run`, `agent.field_edit`, `integration.test`, `assistant.chat`, and admin action (member added/removed, department created, etc.) for the current org, most recent first.

Super admins see cross-org audit via the Platform tab.

## Does the AI keep my data?

Azure OpenAI is configured without training-data retention. Prompts and responses are not used to train models. The hub stores them in your DB for audit purposes — but only within your org, only visible to your org's admins.

## Why is my file upload rejected?

Accepted types are `.pdf`, `.doc`, `.docx`, `.txt`, `.csv`, `.log` (Investigation) and `.xlsx` (Data Classifier / Master Builder / Enrichment / Duplicates / Lookup). Other formats are dropped silently on upload. Maximum file size per upload is 10 MB.

## How do I give a new colleague access?

Org admins: open **Members** in the sidebar → **Invite member**. Fill in email, name, role, password, and optionally assign departments. The invite creates a user record and a membership row; the colleague logs in with the password you set.

## Can I export a run's data outside the Word report?

Only `.docx` today. The full run JSON (session state, messages, fields) is available via `GET /api/runs/{id}` if your tooling can consume it — useful for pulling data into other systems. Raw SQL access is not exposed.

## I got "SOP Note: …" in an agent reply. Is that a blocker?

No. SOP notes are advisory flags the agent raises when it detects a compliance concern (missing justification for a short historical-check window, human-error-only root cause without systemic analysis, etc.). The draft still exports. Address the note in a follow-up turn or inline edit and the next draft won't carry it.

## How current are these docs?

The User Guide is packaged with the app — the copy you're reading is the version shipped with this build. The Assistant chatbot in the bottom-right reads from the same source, so both stay in sync across releases.
