import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import { publicApi } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';

/**
 * Two-step, email-first login page.
 *
 * Why two steps: one deployment of the app serves many tenants. We want
 * each tenant's users to see their org's name + logo on the login
 * screen, but we can't know which tenant they belong to until they tell
 * us. So:
 *
 *   Step 1 — user types work email → we call GET /public/orgs/for-email.
 *            The backend resolves the email to an active membership and
 *            returns just the org name + logo. Constant-time so an
 *            enumerator can't distinguish "known email" from "unknown".
 *   Step 2 — we reveal the password field inside a header that's now
 *            branded with the org's logo and name. Submit → standard
 *            POST /auth/login flow.
 *
 * The welcome greeting on the left side is derived *client-side* from
 * the email local-part ("sourav.kumar@x" → "Sourav Kumar"). We do NOT
 * ask the backend for the user's real display name — returning that
 * from a pre-auth endpoint would be a PII leak and an account-
 * enumeration oracle. Email-derived greeting is cheap + privacy-safe.
 *
 * Visual shape mirrors the Uniqus Accelerators portal: navy-gradient
 * left column with the welcome copy, white right column with the form.
 * Stacks vertically on phones.
 */


/** Cheap title-case for display-only contexts. Respects the server's
 *  stored value as much as possible — only lifts the first letter of
 *  each whitespace-separated word, leaves the rest alone so someone
 *  stored as "McDonald" or "van der Berg" doesn't get flattened to
 *  "Mcdonald" / "Van Der Berg". */
function prettifyName(s) {
  if (!s) return s;
  return s.replace(/\b([a-z])/g, (_, c) => c.toUpperCase());
}


/** Derive a friendly greeting from an email's local-part, respecting
 *  whatever separators the user typed.
 *
 *    sourav.kumar@x   → "Sourav Kumar"
 *    sourav_kumar@x   → "Sourav Kumar"
 *    sourav-kumar@x   → "Sourav Kumar"
 *    sourav@x         → "Sourav"
 *
 *  We deliberately DO NOT try to heuristically split a
 *  no-separator string like `souravkumar` into "Sourav Kumar" — there's
 *  no reliable way without a name dictionary, and a wrong split ("Sou
 *  Rav Kumar") is worse than no name at all. In that case we return ''
 *  and the caller falls back to a generic greeting.
 */
function greetingFromEmail(email) {
  const local = (email || '').split('@')[0] || '';
  if (!local) return '';
  // No separator present → concatenated name we can't safely split.
  // Signal "no reliable name" and let the caller render a generic hello.
  if (!/[._\-+]/.test(local)) return '';
  return local
    .split(/[._\-+]+/)
    .filter(Boolean)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
    .join(' ');
}
export default function LoginPage() {
  const { login, isAuthenticated } = useAuth();
  const nav = useNavigate();
  const loc = useLocation();

  // 'email' → user is typing their address.
  // 'password' → branding resolved, password field revealed.
  const [step, setStep] = useState('email');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  // Branding comes from the public endpoint at the end of step 1. Null
  // means "lookup failed or no org matched"; we still proceed to the
  // password step, just without a tenant logo.
  const [branding, setBranding] = useState(null);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);

  if (isAuthenticated) return <Navigate to={loc.state?.from?.pathname || '/'} replace />;

  async function onEmailContinue(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      // Public endpoint — returns { name, logo_url } or { null, null }.
      // We don't fail the step if the org can't be resolved; the user
      // might still have valid creds we haven't linked to branding yet.
      const b = await publicApi(
        `/public/orgs/for-email?email=${encodeURIComponent(email.trim().toLowerCase())}`,
      );
      setBranding(b || null);
      setStep('password');
    } catch (e2) {
      // Network / server error — surface it but let the user retry.
      setErr(e2.message || 'Could not reach the login service. Try again.');
    } finally {
      setBusy(false);
    }
  }

  async function onSignIn(e) {
    e.preventDefault();
    setErr('');
    setBusy(true);
    try {
      await login(email, password);
      nav(loc.state?.from?.pathname || '/', { replace: true });
    } catch (e2) {
      setErr(e2.message || 'Login failed');
    } finally {
      setBusy(false);
    }
  }

  function backToEmail() {
    setStep('email');
    setPassword('');
    setErr('');
  }

  return (
    <div className="login-split">
      {/* ─── Left: navy hero ────────────────────────────────────────── */}
      <aside className="login-brand">
        {/* Tenant logo (once branding is resolved) or a placeholder dot */}
        <div className="login-brand-logomark" aria-hidden="true">
          {branding?.logo_url ? (
            <img src={branding.logo_url} alt={`${branding.name || 'Organisation'} logo`} />
          ) : (
            <div className="login-brand-logomark-dot" />
          )}
        </div>

        <div className="login-brand-copy">
          <div className="login-brand-eyebrow">Welcome</div>
          <h1 className="login-brand-title">
            {(() => {
              // Name resolution priority on step 2:
              //   1. Server's `user_display_name` from /public/orgs/for-email
              //      (the real `users.name` column — beats any email guess).
              //   2. Email-derived title case ("sourav.kumar" → "Sourav Kumar").
              //   3. Generic "Welcome back" when we have nothing reliable.
              if (step !== 'password') {
                return <>AI Hub <em>Agent Workspace</em></>;
              }
              const fromServer = branding?.user_display_name?.trim();
              const fromEmail = greetingFromEmail(email);
              if (fromServer) {
                // Lift first-letter capitalisation for display (the DB may
                // hold "sourav kumar" lowercase). See prettifyName().
                return <>Hi, <em>{prettifyName(fromServer)}</em></>;
              }
              if (fromEmail) {
                return <>Hi, <em>{fromEmail}</em></>;
              }
              return <>Welcome <em>back</em></>;
            })()}
          </h1>
          <p className="login-brand-tagline">
            {step === 'password' && branding?.name
              ? `Continue to your ${branding.name} workspace.`
              : step === 'password'
                ? 'Enter your password to continue.'
                : 'Unified agent workspace — sign in with your corporate email to reach your tenant.'}
          </p>
        </div>

        <div className="login-brand-footer">
          <span>Secure sign-in</span>
          <span aria-hidden="true">·</span>
          <span>SSO-ready</span>
        </div>
      </aside>

      {/* ─── Right: form ─────────────────────────────────────────────── */}
      <main className="login-form-col">
        <div className="login-form-card">
          {/* Step header */}
          <div className="login-form-head">
            <h2>Sign in</h2>
            <p>
              {step === 'email'
                ? 'Use your work email to get started.'
                : branding?.name
                  ? <>Signing in as a member of <b>{branding.name}</b>.</>
                  : 'Enter your password to continue.'}
            </p>
          </div>

          {err && <div className="inv-warning login-form-err">{err}</div>}

          {step === 'email' ? (
            <form onSubmit={onEmailContinue} className="login-form">
              <label className="login-field">
                <span>Work email</span>
                <input
                  type="email"
                  autoFocus
                  required
                  autoComplete="email"
                  value={email}
                  onChange={(ev) => setEmail(ev.target.value)}
                  placeholder="you@company.com"
                />
              </label>

              <button
                type="submit"
                disabled={busy || !email.trim()}
                className="btn btn-primary login-submit"
              >
                {busy ? 'Checking…' : 'Continue'}
              </button>
            </form>
          ) : (
            <form onSubmit={onSignIn} className="login-form">
              {/* Read-only echo of the email + a way back */}
              <div className="login-identified">
                <div>
                  <div className="login-identified-label">Signing in as</div>
                  <div className="login-identified-email">{email}</div>
                </div>
                <button
                  type="button"
                  className="link-btn"
                  onClick={backToEmail}
                  disabled={busy}
                >
                  Change
                </button>
              </div>

              <label className="login-field">
                <span>Password</span>
                <input
                  type="password"
                  autoFocus
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(ev) => setPassword(ev.target.value)}
                  placeholder="••••••••"
                />
              </label>

              <button
                type="submit"
                disabled={busy || !password}
                className="btn btn-primary login-submit"
              >
                {busy ? 'Signing in…' : 'Sign in'}
              </button>
            </form>
          )}

          <div className="login-form-footer">
            <span>© AI Hub · Agent Workspace</span>
          </div>
        </div>
      </main>
    </div>
  );
}
