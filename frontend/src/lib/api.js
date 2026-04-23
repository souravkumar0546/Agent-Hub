import { humanizeError } from './errors.js';

const TOKEN_KEY = 'sah.token';
const ORG_KEY = 'sah.orgId';

// API base URL. In dev this is empty and Vite's proxy handles `/api/*`.
// In production, set VITE_API_BASE to the backend origin (e.g.
// "https://uniqus-hub-api.onrender.com") so the browser calls the backend
// directly instead of relying on a static-site rewrite. Backend CORS is
// already configured to allow the frontend origin.
const API_BASE = import.meta.env.VITE_API_BASE || '';

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}
export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export function getOrgId() {
  const v = localStorage.getItem(ORG_KEY);
  return v ? Number(v) : null;
}
export function setOrgId(id) {
  if (id) localStorage.setItem(ORG_KEY, String(id));
  else localStorage.removeItem(ORG_KEY);
}

function authHeaders(extra = {}) {
  // Start with the session defaults (auth + active org from localStorage), then
  // let the caller overwrite individual headers via `extra`. The platform-level
  // matrix UI needs to target a *different* org per request (e.g. enabling an
  // agent in org 7 while the super admin's own session has no org selected),
  // so caller-supplied `X-Org-Id` must win.
  const token = getToken();
  const orgId = getOrgId();
  const base = {};
  if (token) base.Authorization = `Bearer ${token}`;
  if (orgId) base['X-Org-Id'] = String(orgId);
  return { ...base, ...extra };
}

async function raiseForStatus(res, data) {
  // Compose an Error whose `message` is the friendly one-liner produced by
  // the shared humanizer (H25). Raw data is preserved on `err.data` so
  // devtools / observability tooling can still see exactly what the server
  // returned. Known-status copy wins over server `detail` strings; unknown
  // cases fall back to the server's detail when it's short + safe.
  const rawDetail = typeof data === 'object' && data ? data.detail : undefined;
  // Build a preliminary error carrying status + data so humanizeError can
  // branch off the HTTP code. We intentionally don't include the raw detail
  // in the Error's own message argument here — humanizeError does the copy.
  const err = new Error('');
  err.status = res.status;
  err.data = data;
  err.detail = rawDetail;
  err.message = humanizeError(err);
  throw err;
}

export async function api(path, { method = 'GET', body, headers = {} } = {}) {
  const h = authHeaders({ 'Content-Type': 'application/json', ...headers });

  const res = await fetch(`${API_BASE}/api${path}`, {
    method,
    headers: h,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return null;

  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await res.json() : await res.text();
  if (!res.ok) await raiseForStatus(res, data);
  return data;
}


/** Unauthenticated fetch — skips the Authorization / X-Org-Id headers.
 *
 * Used by the pre-login branding lookup (`GET /public/orgs/for-email`):
 * the login page has no token yet, and sending stale headers from an
 * expired session would confuse the server. Keep this helper narrow —
 * anything that requires auth should use `api()`.
 */
export async function publicApi(path, { method = 'GET', body, headers = {} } = {}) {
  const res = await fetch(`${API_BASE}/api${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', ...headers },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 204) return null;
  const ct = res.headers.get('content-type') || '';
  const data = ct.includes('application/json') ? await res.json() : await res.text();
  if (!res.ok) await raiseForStatus(res, data);
  return data;
}

/** Multipart POST — caller passes a FormData. */
export async function apiForm(path, formData) {
  const h = authHeaders();
  const res = await fetch(`${API_BASE}/api${path}`, { method: 'POST', headers: h, body: formData });
  const ct = res.headers.get('content-type') || '';

  // Read the body as text first so we can handle parse errors gracefully.
  const raw = await res.text();
  let data = raw;
  if (ct.includes('application/json')) {
    try {
      data = JSON.parse(raw);
    } catch (e) {
      // Known quirk: server has occasionally returned non-strict JSON for run
      // payloads containing control bytes from legacy .doc uploads. Surface the
      // parse error so the caller can fall back to GET /runs/{id}.
      const err = new Error('parse_error');
      err.status = res.status;
      err.raw = raw;
      throw err;
    }
  }
  if (!res.ok) await raiseForStatus(res, data);
  return data;
}

/** Build an authenticated download URL for a given API path. Used for DOCX export. */
export function downloadHref(path) {
  // Vite proxies /api/* to the backend — include auth via a one-shot fetch that
  // opens the resulting blob in a new tab.
  return `${API_BASE}/api${path}`;
}

/** Fetch a binary file with auth headers, open it as a download in the browser. */
export async function downloadFile(path, fallbackName = 'download') {
  const h = authHeaders();
  const res = await fetch(`${API_BASE}/api${path}`, { headers: h });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(txt || `HTTP ${res.status}`);
  }
  const blob = await res.blob();
  const cd = res.headers.get('content-disposition') || '';
  const match = cd.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallbackName;

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
