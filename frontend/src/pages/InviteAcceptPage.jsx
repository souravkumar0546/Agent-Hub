import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { setOrgId, setToken } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';

/** Public page (no auth) that invitees land on from the link in their email. */
export default function InviteAcceptPage() {
  const { token } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, refresh } = useAuth();

  const [invite, setInvite] = useState(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [busy, setBusy] = useState(false);
  const [accepted, setAccepted] = useState(false);

  // Load invite details. This is a public endpoint (no auth header needed).
  useEffect(() => {
    setLoading(true);
    fetch(`/api/invites/${encodeURIComponent(token)}`)
      .then(async (r) => {
        const data = await r.json();
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        return data;
      })
      .then(setInvite)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  async function submit(e) {
    e.preventDefault();
    if (password.length < 8) {
      setErr('Password must be at least 8 characters.');
      return;
    }
    if (password !== confirm) {
      setErr('Passwords do not match.');
      return;
    }
    setBusy(true);
    setErr('');
    try {
      const res = await fetch(`/api/invites/${encodeURIComponent(token)}/accept`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || `HTTP ${res.status}`);

      // Log the new user straight in.
      setToken(data.access_token);
      if (data.org_id) setOrgId(data.org_id);
      if (refresh) await refresh();
      setAccepted(true);
      // Small delay so the success state renders before navigating.
      setTimeout(() => navigate('/', { replace: true }), 800);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  // Already signed in? Bounce home — accepting an invite while authenticated
  // is ambiguous (which account is joining?). Make them log out first.
  if (isAuthenticated && !accepted) {
    return <Navigate to="/" replace />;
  }

  const bgStyle = {
    display: 'grid', placeItems: 'center', height: '100vh', background: 'var(--bg)',
  };
  const cardStyle = {
    width: 440, padding: 40, background: 'var(--bg-elev)',
    border: '1px solid var(--border)', borderRadius: 12,
  };

  return (
    <div style={bgStyle}>
      <div style={cardStyle}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 24 }}>
          <div style={{ width: 36, height: 36, borderRadius: '50%', background: 'var(--accent)' }} />
          <div>
            <div style={{ fontFamily: 'var(--serif)', fontStyle: 'italic', fontSize: 22 }}>AI Hub</div>
            <div style={{ fontSize: 10, letterSpacing: '0.18em', color: 'var(--ink-muted)' }}>ACCEPT INVITATION</div>
          </div>
        </div>

        {loading ? (
          <div className="empty">Loading invite…</div>
        ) : err && !invite ? (
          <div className="inv-warning">{err}</div>
        ) : invite && invite.status !== 'pending' ? (
          <>
            <h1 style={{ fontSize: 20, fontWeight: 500, marginBottom: 8 }}>
              {invite.status === 'accepted' ? 'This invite has already been used' :
               invite.status === 'revoked'  ? 'This invite was revoked' :
                                              'This invite has expired'}
            </h1>
            <p style={{ color: 'var(--ink-dim)', fontSize: 13 }}>
              Ask {invite.invited_by || 'your admin'} to send a new one.
            </p>
          </>
        ) : accepted ? (
          <>
            <h1 style={{ fontSize: 20, fontWeight: 500, marginBottom: 8 }}>Welcome, {invite.name.split(' ')[0]}.</h1>
            <p style={{ color: 'var(--ink-dim)', fontSize: 13 }}>
              Signing you in…
            </p>
          </>
        ) : invite ? (
          <form onSubmit={submit}>
            <h1 style={{ fontSize: 20, fontWeight: 500, marginBottom: 6 }}>
              You've been invited
            </h1>
            <p style={{ color: 'var(--ink-dim)', fontSize: 13, marginBottom: 20 }}>
              <b style={{ color: 'var(--ink)' }}>{invite.invited_by || 'An admin'}</b> invited you to join{' '}
              <b style={{ color: 'var(--ink)' }}>{invite.org_name || 'the platform'}</b>{' '}
              as <b style={{ color: 'var(--accent)' }}>{invite.role}</b>. Choose a password to finish sign-up.
            </p>

            <div style={{ fontSize: 11, color: 'var(--ink-muted)', letterSpacing: '0.04em', marginBottom: 4 }}>EMAIL</div>
            <div style={{ padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 4, fontSize: 14, marginBottom: 14 }}>
              {invite.email}
            </div>

            <label style={{ display: 'block', fontSize: 11, color: 'var(--ink-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>
              Password
            </label>
            <input
              type="password"
              autoFocus
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--ink)', borderRadius: 4, fontSize: 14, outline: 'none', marginBottom: 12 }}
              placeholder="Min 8 characters"
            />

            <label style={{ display: 'block', fontSize: 11, color: 'var(--ink-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 6 }}>
              Confirm password
            </label>
            <input
              type="password"
              required
              minLength={8}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              style={{ width: '100%', padding: '10px 12px', background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--ink)', borderRadius: 4, fontSize: 14, outline: 'none' }}
            />

            {err && (
              <div style={{ color: 'var(--err)', fontSize: 12, marginTop: 12, padding: '8px 10px', background: 'rgba(242,123,123,.08)', borderRadius: 4 }}>
                {err}
              </div>
            )}

            <button type="submit" disabled={busy} className="btn btn-primary" style={{ width: '100%', marginTop: 20, justifyContent: 'center' }}>
              {busy ? 'Creating your account…' : 'Accept invite & sign in'}
            </button>
          </form>
        ) : null}
      </div>
    </div>
  );
}
