# Deploying Syngene AI Hub to Render

Everything — managed Postgres, FastAPI backend, Vite static frontend — comes
up from a single `render.yaml` Blueprint. No Dockerfiles, no separate services
to stitch together.

**Cost, starter tier:** ~$14/month (Postgres $7 + backend web service $7).
The static frontend is free on Render. Free-tier backend exists but cold-starts
after 15 min of idle; the $7 starter stays always-on.

**Time to first URL:** ~10 minutes once you have a GitHub repo pointing at this
code.

---

## Step 1 — get the code to GitHub

If you don't already have a repo:

```bash
cd /path/to/syngene-ai-hub
git init -b main
git add .
git commit -m "initial commit"
# Create an empty repo on GitHub first, then:
git remote add origin https://github.com/<you>/<repo>.git
git push -u origin main
```

Verify `.env`, `venv/`, `node_modules/`, and `dma_master/` are NOT in the
commit — the `.gitignore` at repo root excludes them. Run `git status` before
the first push; if any of those show up as staged, delete them and re-stage.

---

## Step 2 — connect Render

1. Dashboard → **New** → **Blueprint**.
2. Connect the GitHub repo.
3. Render reads `render.yaml` from the repo root and shows a preview:
   - **Postgres** `syngene-hub-db`
   - **Web service** `syngene-hub-api` (backend)
   - **Static site** `syngene-hub` (frontend)
4. Click **Apply**.

Provisioning the database takes ~2 minutes. The backend's first build takes
~3 minutes (pip install, alembic migrate, first worker boot). Frontend
static build takes ~90 seconds.

---

## Step 3 — fill the secret env vars

Go to the backend service (`syngene-hub-api`) → **Environment** tab → paste
values for every row marked `(set by user)`:

| Variable | What to paste |
|---|---|
| `BOOTSTRAP_SUPER_ADMIN_EMAIL` | your admin email, e.g. `admin@yourco.com` |
| `BOOTSTRAP_SUPER_ADMIN_PASSWORD` | a strong password (≥ 12 chars). You'll log in with this on first boot. |
| `BOOTSTRAP_SUPER_ADMIN_NAME` | display name for the super admin, e.g. `Platform Admin` |
| `AZURE_OPENAI_ENDPOINT` | your Azure Foundry endpoint, e.g. `https://<tenant>.cognitiveservices.azure.com` |
| `AZURE_OPENAI_API_KEY` | rotate-fresh key from Azure Foundry — **do NOT reuse the one from local `.env`** |
| `AZURE_OPENAI_DEPLOYMENT` | e.g. `gpt-5.3-chat` (used by the RCA engine) |
| `AZURE_OPENAI_MODEL` | e.g. `gpt-4o-mini` (used by DMA services) |

Save; Render redeploys automatically.

`JWT_SECRET` and `INTEGRATIONS_SECRET_KEY` don't appear here because
`render.yaml` has Render generate strong random values on first deploy
(`generateValue: true`). Don't override them.

`DATABASE_URL` is also invisible in the list because it's wired from the
Postgres service automatically.

---

## Step 4 — verify

- Backend health: `https://syngene-hub-api.onrender.com/api/health` → `{"status":"ok"}`
- Frontend: `https://syngene-hub.onrender.com` → login screen.
- Sign in with the `BOOTSTRAP_SUPER_ADMIN_EMAIL` + `BOOTSTRAP_SUPER_ADMIN_PASSWORD` you pasted.

If the frontend loads but login fails with a network error, check the backend
logs (Render dashboard → service → Logs) — most likely `alembic upgrade head`
failed or the Azure env vars are missing.

---

## Known limitations (accept for the demo, fix before real customers)

1. **RCA runs are synchronous on the HTTP request.** Render's edge proxy has
   ~110s request timeout. A chatty RCA turn (60-80s typical) will usually
   land inside that window, but an especially long one can 504. Readiness
   audit item **C10** — move to a background queue (arq + Redis is the
   cheapest path on Render) before any load testing.

2. **Ephemeral disk.** The backend writes `backend/dma_master/*.xlsx` and
   `_taxonomy_overrides/*.json` to local disk. Render's Web Service disk
   resets on every deploy and on scale events. For the demo this just means
   master data doesn't persist across re-deploys. Fix: attach a Render Disk
   ($1/GB/month) to the backend service, mount at `backend/dma_master/`, OR
   migrate the store to S3.

3. **Rename pitfall.** `render.yaml` hard-codes the backend URL
   (`syngene-hub-api.onrender.com`) inside the frontend's `/api/*` rewrite
   destination. If you rename the backend service, update the `destination:`
   line in `render.yaml` and re-apply the Blueprint.

4. **No CDN in front of the backend.** `syngene-hub-api` serves all API calls
   directly. Fine at demo traffic. At scale, put Cloudflare in front.

5. **No refresh tokens, no session revocation.** JWT lifetime is 24 h
   (`JWT_EXPIRES_MINUTES=1440`). This is audit item **H1**. Users who hit
   expiry see random errors until they manually sign out. Shorten + add a
   refresh flow before prod.

6. **Azure key rotation requires a restart.** `core/ai_engine.py:154-156`
   caches the `AsyncAzureOpenAI` client with `lru_cache`; if you rotate the
   key in Azure Foundry, redeploy the Render service to pick it up. Audit
   item **H7**.

---

## Rolling back

- Postgres migrations have `downgrade()` paths except for the baseline
  (which leaks an ENUM type — audit item **M3**). Don't `alembic downgrade base`
  on a live DB without reading `backend/alembic/versions/2d96c27c85f2_baseline.py`
  first.
- To roll the backend back to a previous commit: Render dashboard → service →
  **Manual Deploy** → pick an earlier commit SHA.
- Frontend rollback is identical — pick the old commit, redeploy the static
  build.

---

## Custom domain

Render dashboard → frontend service → **Settings** → **Custom Domains** →
add `app.yourco.com`. Update DNS at your registrar (CNAME to the
`*.onrender.com` host Render shows). HTTPS cert issued automatically.

After adding a custom domain, update the backend's `CORS_ORIGINS` env var
to include both the Render domain AND the custom domain, comma-separated:

```
https://syngene-hub.onrender.com,https://app.yourco.com
```

---

## Auto-deploy

Render watches the linked branch (default: `main`). Every `git push` triggers
a rebuild. Disable via **Settings → Auto-Deploy** if you want manual control.
