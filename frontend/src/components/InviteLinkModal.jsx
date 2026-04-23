import { useMemo, useState } from 'react';

/** Copy-link modal shown after an invite is created. */
export default function InviteLinkModal({ invite, onClose }) {
  const [copied, setCopied] = useState(false);
  const inviteUrl = useMemo(() => {
    // The backend hands us a relative path (/invite/<token>); resolve to
    // an absolute URL using the current origin.
    if (!invite?.invite_url) return '';
    if (/^https?:\/\//.test(invite.invite_url)) return invite.invite_url;
    const origin = typeof window !== 'undefined' ? window.location.origin : '';
    return `${origin}${invite.invite_url}`;
  }, [invite]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (_) {
      // Fallback: select the input — browsers without clipboard API.
    }
  }

  if (!invite) return null;

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      display: 'grid', placeItems: 'center', zIndex: 100,
    }}>
      <div style={{
        width: 520, maxWidth: 'calc(100vw - 32px)',
        background: 'var(--bg-elev)', border: '1px solid var(--border-strong)',
        borderRadius: 12, padding: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 500, marginBottom: 4 }}>Invitation created</h2>
            <p style={{ fontSize: 13, color: 'var(--ink-dim)', margin: 0 }}>
              Share this link with <b style={{ color: 'var(--ink)' }}>{invite.email}</b>. It expires{' '}
              {invite.expires_at
                ? new Date(invite.expires_at).toLocaleDateString([], { dateStyle: 'medium' })
                : 'in 14 days'}.
            </p>
          </div>
          {/* M34: modal dismiss uses the dedicated .modal-close button style
              rather than a linkified "Close ×" — matches the IntegrationsPage
              and ConfirmDialog pattern. */}
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div style={{
          display: 'flex', gap: 8, alignItems: 'stretch',
          background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 6, padding: 6,
        }}>
          <input
            value={inviteUrl}
            readOnly
            onFocus={(e) => e.target.select()}
            style={{
              flex: 1, background: 'transparent', border: 0,
              color: 'var(--ink)', fontFamily: 'var(--mono)', fontSize: 12,
              padding: '6px 8px', outline: 'none',
            }}
          />
          <button className="btn btn-primary" onClick={copy} style={{ minWidth: 80, justifyContent: 'center' }}>
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>
    </div>
  );
}
