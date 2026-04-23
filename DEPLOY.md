# Deploying Uniqus AI Hub to Render

Everything — FastAPI backend, Vite static frontend — comes up from a single
`render.yaml` Blueprint. Postgres is **external** (Neon free tier) so the
whole stack runs without a credit card on file.

**Cost as configured:** $0/month.
- Backend: Render free web service (cold-starts after 15 min idle, ~30-60s
  first request to warm up)
- Frontend: Render static site (free forever, always-on)
- Postgres: Neon free tier (0.5 GB storage, always-on, no cold starts)

**When to upgrade:** the moment you have paying users or need consistent
latency. Swap backend to Render `starter` ($7/mo, always-on) and either stay on
Neon or move to Render's managed Postgres (also $7/mo) — both paths are one
`render.yaml` edit, see the comment at the top of the file.

**Time to first URL:** ~15 minutes once you have a GitHub repo.

---

## Step 1 — get the code to GitHub

If you don't already have a repo:

```bash
cd /path/to/uniqus-ai-hub
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

## Step 2a — spin up Postgres on Neon

1. Go to https://neon.tech, sign in (GitHub works), **Create project**.
2. Project name: `uniqus-hub`. Region: pick one close to where your
   Render services will live (Render's free tier is typically Oregon or
   Frankfurt). Neon regions: US East, US West, or Europe Frankfurt.
   If unsure, **US East**.
3. Postgres version: 16 (matches what we develop against).
4. Once the project is created, Neon opens a **Connection Details** panel.
   Toggle **Pooled connection** and copy the full `postgresql://...`
   string. Example shape:
   ```
   postgresql://user:pw@ep-xxx-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```
   Must include `-pooler.` in the host and `?sslmode=require` on the end.
5. Keep this string in your clipboard — you'll paste it in step 3.

Why pooled: Neon's free tier has a low direct-connection limit; the
pooler brokers connections. FastAPI's connection pool on top of the
Neon pooler is the supported pattern.

## Step 2b — connect Render

1. Dashboard → **New** → **Blueprint**.
2. Connect the GitHub repo.
3. Render reads `render.yaml` from the repo root and shows a preview:
   - **Web service** `uniqus-hub-api` (backend, free plan)
   - **Static site** `uniqus-hub` (frontend, free)
4. Click **Apply**. No card required — every service is free.

Backend's first build takes ~3 minutes (pip install, alembic migrate
against Neon, first worker boot). Frontend static build takes ~90 seconds.

---

## Step 3 — fill the secret env vars

Go to the backend service (`uniqus-hub-api`) → **Environment** tab → paste
values for every variable marked `sync: false` in `render.yaml`:

| Variable | What to paste |
|---|---|
| `DATABASE_URL` | The pooled Neon connection string from step 2a (ends with `?sslmode=require`, host contains `-pooler.`) |
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

---

## Step 4 — verify

- Backend health: `https://uniqus-hub-api.onrender.com/api/health` → `{"status":"ok"}`
- Frontend: `https://uniqus-hub.onrender.com` → login screen.
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
   (`uniqus-hub-api.onrender.com`) inside the frontend's `/api/*` rewrite
   destination. If you rename the backend service, update the `destination:`
   line in `render.yaml` and re-apply the Blueprint.

4. **No CDN in front of the backend.** `uniqus-hub-api` serves all API calls
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
https://uniqus-hub.onrender.com,https://app.yourco.com
```

---

## Auto-deploy

Render watches the linked branch (default: `main`). Every `git push` triggers
a rebuild. Disable via **Settings → Auto-Deploy** if you want manual control.
