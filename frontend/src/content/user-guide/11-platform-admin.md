# Platform administration (super admin)

This section is for **super admins** only. Org admins and members can skip it.

## Onboarding a new organisation

1. Sidebar → **Platform** → **Organizations** → **+ New organisation**.
2. Enter the org name and slug (used for the tenant URL — e.g. `slug=acme` → branding lookup keys it on `acme`).
3. Upload a logo if available (≤ 1 MB PNG / JPG; the URL must be `https://`).
4. Save. The new org has zero members. Open it via the **Open →** action and invite an org admin.

When you "open" an org as super admin, the platform stores a session flag so the rest of the UI behaves as if you were that org's admin — useful for impersonation-debugging.

## Cross-org agent catalog

**Platform → Agents** is a matrix: rows are organisations, columns are agents. Use the toggle to grant or revoke an agent for a tenant — this controls the `granted_by_platform` flag. Org admins still need to flip `is_enabled` to expose it to their members; the two-gate system means you can pre-grant capability without surprising anyone.

## Suspending an organisation

Platform → Organizations → row → **Edit** → **Active** toggle off. Members of that org are immediately blocked from signing in (`require_org` returns a generic 403). Their data is preserved.

To restore: flip Active back on. To delete an org permanently, contact engineering — the cascade is non-trivial (runs, audit, integrations, departments, members).

## Custom URLs

Render auto-issues TLS for any custom domain you attach to the static site or backend service. After DNS propagates, update `CORS_ORIGINS` on the backend and `VITE_API_BASE` on the frontend (then trigger a "Clear build cache & deploy" because Vite inlines env vars at build time).

## Limits to remember

- **JWT lifetime**: 24 h. No refresh tokens yet — users will need to re-login daily.
- **RCA timeout**: Render's edge times out at ~110 s. A long RCA turn can hit this; Devio is supposed to chunk requests under that.
- **Bootstrap super admin**: created on first boot from `BOOTSTRAP_SUPER_ADMIN_*` env vars. If you delete that user, they'll be re-created on next backend restart.
