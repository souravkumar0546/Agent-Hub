/**
 * Friendly error copy mapper.
 *
 * Before this shipped, `setErr(e.message)` across the app rendered the
 * backend's raw `detail` string verbatim. Ordinary FastAPI validation
 * errors serialise as a stringified array of `{loc, msg, type, input}`
 * objects — unreadable. Stack-trace-ish strings (from any `raise
 * Exception(...)` path upstream) also leaked through. H25 in the April
 * 2026 readiness review.
 *
 * This module centralises the mapping. Callers just pass the caught
 * `Error` and get back a short, human-friendly string safe to render.
 * The raw `detail` is still available on `err.data` / `err.message` for
 * devtools; `humanizeError` additionally `console.error`s the full
 * context so it never silently disappears.
 */

/**
 * Turn a thrown `api()` error (or a native `Error`) into a one-liner fit
 * for an `.inv-warning` banner or a toast.
 *
 * Hierarchy of checks:
 *   1. Known HTTP status codes → canned copy per status.
 *   2. Known backend `detail` patterns → slightly-tweaked copy (e.g.
 *      "slug already exists" → "That slug is taken.").
 *   3. A single short string `detail` that doesn't look like a stack
 *      trace → pass through as-is (server-authored messages are usually
 *      fine).
 *   4. Anything else (Pydantic array, long multi-line, bare Error) →
 *      generic "Something went wrong — please try again."
 */
export function humanizeError(err) {
  // Always preserve the full error for developers.
  // eslint-disable-next-line no-console
  console.error('[api error]', err);

  if (!err) return GENERIC_MESSAGE;

  const status = err.status;
  // `err.data?.detail` is what FastAPI returned; fall back to `err.message`
  // which `raiseForStatus` already stringified.
  const rawDetail = err.data?.detail;
  const message = typeof err.message === 'string' ? err.message : '';

  // 1. Status-first copy. These win over detail parsing so we don't leak
  //    Python traceback text to end users.
  if (status === 401) {
    // 401 is both "session expired" and "login credentials rejected". If the
    // server sent a short, non-trace `detail` mentioning credentials / bad
    // token, surface it — users need to know their password was wrong, not
    // that their session expired.
    if (includesAny(rawDetail, ['invalid email', 'invalid password', 'invalid credentials', 'incorrect password', 'missing bearer'])) {
      return typeof rawDetail === 'string' ? rawDetail : 'Your email or password is incorrect.';
    }
    return 'Your session has expired \u2014 please sign in again.';
  }
  if (status === 403) {
    // Common org-context gate from deps.get_org_context (H3). Surface with
    // friendlier phrasing; the server's exact string is fine if short.
    if (includesAny(rawDetail, ['not available', 'suspended'])) {
      return 'This organisation is suspended or unavailable.';
    }
    if (includesAny(rawDetail, ['super_admin', 'super admin'])) {
      return 'This action requires a platform super-admin.';
    }
    if (includesAny(rawDetail, ['org_admin', 'org admin'])) {
      return 'This action requires an organisation admin.';
    }
    if (includesAny(rawDetail, ['member of this organization', 'not a member'])) {
      return 'You don\u2019t have access to this organisation.';
    }
    if (includesAny(rawDetail, ['not been granted'])) {
      return 'This agent hasn\u2019t been granted to your organisation yet. Ask your platform administrator to enable it.';
    }
    return 'You don\u2019t have permission to do that.';
  }
  if (status === 404) return 'We couldn\u2019t find what you were looking for.';
  if (status === 409) {
    // Typical conflicts: slug already exists, agent already installed, etc.
    if (includesAny(rawDetail, ['slug already exists'])) return 'That slug is already in use.';
    if (includesAny(rawDetail, ['already installed'])) return 'That agent is already installed.';
    if (includesAny(rawDetail, ['already exists'])) return 'That already exists.';
    return typeof rawDetail === 'string' ? rawDetail : 'That conflicts with an existing record.';
  }
  if (status === 413 || includesAny(message, ['too large', 'too long'])) {
    return 'That upload is too large. Try a smaller file.';
  }
  if (status === 422) {
    // FastAPI validation — rawDetail is usually an array of {loc,msg,type}.
    // Pull the first msg out; fall back to a generic.
    if (Array.isArray(rawDetail) && rawDetail.length > 0) {
      const first = rawDetail[0];
      if (first && typeof first === 'object' && typeof first.msg === 'string') {
        // Pydantic v2 decorates messages with "Value error, " — strip.
        return first.msg.replace(/^value error,\s*/i, '');
      }
    }
    if (typeof rawDetail === 'string') return rawDetail;
    return 'Some of the details you entered look wrong. Please check and try again.';
  }
  if (status === 429) return 'Too many requests — please slow down and try again.';
  if (typeof status === 'number' && status >= 500) {
    return 'The server hit a snag. Please try again in a moment.';
  }

  // 2. Non-status heuristics. Network-level failures, parse errors, etc.
  if (message === 'parse_error') return 'We couldn\u2019t read the server\u2019s response — please retry.';
  if (includesAny(message, ['failed to fetch', 'networkerror', 'load failed'])) {
    return 'Can\u2019t reach the server. Check your connection and try again.';
  }

  // 3. Short server-authored string detail — safe to surface.
  if (typeof rawDetail === 'string' && rawDetail.length > 0 && rawDetail.length <= 180 && !looksLikeTrace(rawDetail)) {
    return rawDetail;
  }
  if (typeof message === 'string' && message.length > 0 && message.length <= 180 && !looksLikeTrace(message)) {
    return message;
  }

  return GENERIC_MESSAGE;
}


/** Default fallback copy when nothing else matched / safe to surface. */
export const GENERIC_MESSAGE = 'Something went wrong \u2014 please try again.';


// --- Helpers ---------------------------------------------------------------

function includesAny(value, needles) {
  if (value == null) return false;
  const s = (typeof value === 'string' ? value : JSON.stringify(value)).toLowerCase();
  return needles.some((n) => s.includes(n.toLowerCase()));
}

/** Rough heuristic: treats multi-line strings, "Traceback" literals, and
 *  strings containing `File "..."` markers as unsafe to echo verbatim. */
function looksLikeTrace(s) {
  if (typeof s !== 'string') return false;
  if (s.includes('\n')) return true;
  if (s.includes('Traceback')) return true;
  if (/\bFile\s+"[^"]+",\s+line\s+\d+/.test(s)) return true;
  return false;
}
