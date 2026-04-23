import { useCallback, useEffect, useState } from 'react';
import AppShell from '../components/AppShell.jsx';
import { api } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';
import { useTheme } from '../lib/theme.jsx';


/** Two-button pill for picking the colour theme. */
function ThemeSwitcher() {
  const { theme, setTheme } = useTheme();
  return (
    <div className="theme-switch" role="group" aria-label="Colour theme">
      <button
        type="button"
        className={`theme-switch-opt${theme === 'dark' ? ' active' : ''}`}
        onClick={() => setTheme('dark')}
        aria-pressed={theme === 'dark'}
      >
        Dark
      </button>
      <button
        type="button"
        className={`theme-switch-opt${theme === 'light' ? ' active' : ''}`}
        onClick={() => setTheme('light')}
        aria-pressed={theme === 'light'}
      >
        Light
      </button>
    </div>
  );
}


function Row({ label, children }) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: '200px 1fr',
      alignItems: 'center',
      padding: '12px 0',
      borderBottom: '1px solid var(--border)',
      gap: 14,
    }}>
      <div style={{ fontSize: 11, color: 'var(--ink-muted)', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
        {label}
      </div>
      <div style={{ fontSize: 14, color: 'var(--ink)', minWidth: 0 }}>{children}</div>
    </div>
  );
}


function SectionHeading({ children, sub }) {
  return (
    <div style={{ margin: '32px 0 14px' }}>
      <h2 style={{
        fontSize: 14, color: 'var(--ink-dim)', letterSpacing: '0.06em',
        textTransform: 'uppercase', fontWeight: 500, marginBottom: 4,
      }}>
        {children}
      </h2>
      {sub && <div style={{ fontSize: 12, color: 'var(--ink-muted)' }}>{sub}</div>}
    </div>
  );
}


/** Inline-edit org name. Appears only for ORG_ADMIN. */
function OrgNameEditor({ org, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(org?.name || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  async function save() {
    if (!name.trim() || name === org.name) {
      setEditing(false);
      return;
    }
    setBusy(true);
    setErr('');
    try {
      await api('/orgs/current', { method: 'PATCH', body: { name: name.trim() } });
      setEditing(false);
      if (onSaved) await onSaved();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!editing) {
    return (
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}>
        <span>{org?.name || '—'}</span>
        <button className="link-btn" onClick={() => setEditing(true)}>Edit</button>
      </div>
    );
  }
  return (
    <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <input
        value={name}
        onChange={(e) => setName(e.target.value)}
        autoFocus
        style={{
          flex: 1, background: 'var(--bg)', border: '1px solid var(--border-strong)',
          color: 'var(--ink)', padding: '7px 10px', borderRadius: 4, fontSize: 14, outline: 'none',
        }}
      />
      <button className="btn btn-primary" onClick={save} disabled={busy}>
        {busy ? 'Saving…' : 'Save'}
      </button>
      <button className="btn" onClick={() => { setEditing(false); setName(org.name); }} disabled={busy}>
        Cancel
      </button>
      {err && <div className="inv-warning" style={{ marginLeft: 8 }}>{err}</div>}
    </div>
  );
}


/** Shows a tiny preview of the org logo + optional URL editor for admins. */
function OrgLogoEditor({ org, editable, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [url, setUrl] = useState(org?.logo_url || '');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const preview = editing ? url : (org?.logo_url || '');

  async function save() {
    setBusy(true);
    setErr('');
    try {
      await api('/orgs/current', {
        method: 'PATCH',
        body: { logo_url: url.trim() },  // "" clears
      });
      setEditing(false);
      if (onSaved) await onSaved();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'center', width: '100%' }}>
      <OrgLogoThumb url={preview} name={org?.name} size={36} />
      {editing ? (
        <>
          <input
            type="url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            autoFocus
            placeholder="https://…/logo.png"
            style={{
              flex: 1, background: 'var(--bg)', border: '1px solid var(--border-strong)',
              color: 'var(--ink)', padding: '7px 10px', borderRadius: 4, fontSize: 13,
              fontFamily: 'var(--mono)', outline: 'none',
            }}
          />
          <button className="btn btn-primary" onClick={save} disabled={busy}>{busy ? 'Saving…' : 'Save'}</button>
          <button
            className="btn"
            disabled={busy}
            onClick={() => { setEditing(false); setUrl(org?.logo_url || ''); setErr(''); }}
          >Cancel</button>
        </>
      ) : (
        <>
          {/* Display mode: the thumb (rendered above) speaks for itself.
              Only surface a label when there's nothing to show. */}
          <div style={{ flex: 1, minWidth: 0, color: 'var(--ink-muted)', fontSize: 13 }}>
            {org?.logo_url ? '' : 'No logo set'}
          </div>
          {editable && (
            <button className="link-btn" onClick={() => setEditing(true)}>
              {org?.logo_url ? 'Replace' : 'Add'}
            </button>
          )}
        </>
      )}
      {err && <div className="inv-warning" style={{ marginLeft: 8 }}>{err}</div>}
    </div>
  );
}


/** Small square thumbnail — logo image if set, monogram fallback otherwise. */
function OrgLogoThumb({ url, name, size = 36 }) {
  const [failed, setFailed] = useState(false);
  const letter = (name || '?').trim().charAt(0).toUpperCase();

  const base = {
    width: size, height: size, borderRadius: size / 4,
    border: '1px solid var(--border)',
    background: 'var(--bg)',
    flexShrink: 0,
    overflow: 'hidden',
    display: 'grid', placeItems: 'center',
  };

  if (url && !failed) {
    return (
      <div style={base}>
        <img
          src={url}
          alt={name || 'Org logo'}
          onError={() => setFailed(true)}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        />
      </div>
    );
  }
  return (
    <div style={{
      ...base,
      background: 'rgba(var(--accent-rgb), 0.1)',
      color: 'var(--accent)',
      fontFamily: 'var(--serif)', fontStyle: 'italic',
      fontSize: size * 0.48, fontWeight: 500,
    }}>
      {letter}
    </div>
  );
}


export default function SettingsPage() {
  const { user, refresh, isOrgAdmin, isSuperAdmin } = useAuth();
  const [org, setOrg] = useState(null);
  const [err, setErr] = useState('');

  const loadOrg = useCallback(async () => {
    if (!user?.current_org_id) {
      setOrg(null);
      return;
    }
    try {
      const o = await api('/orgs/current');
      setOrg(o);
      setErr('');
    } catch (e) {
      setErr(e.message);
    }
  }, [user?.current_org_id]);
  useEffect(() => { loadOrg(); }, [loadOrg]);

  const myDepts = user?.departments || [];

  return (
    <AppShell crumbs={['Settings']}>
      <h1 className="page-title" style={{ marginBottom: 4 }}>
        Settings
      </h1>
      <p className="page-subtitle" style={{ marginBottom: 0 }}>
        Your profile and organisation details.
        {isOrgAdmin && !isSuperAdmin && ' As an org admin you can edit the organisation here; invite members from the Members page.'}
      </p>

      {err && <div className="inv-warning" style={{ marginTop: 14 }}>{err}</div>}

      <SectionHeading>My profile</SectionHeading>
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '4px 18px' }}>
        <Row label="Name">{user?.name}</Row>
        <Row label="Email">{user?.email}</Row>
        <Row label="Role">
          <span className="cap-tag cap-tag--accent">
            {user?.is_super_admin
              ? 'SUPER_ADMIN'
              : (user?.current_org_role || 'MEMBER')}
          </span>
        </Row>
        {/* Departments only make sense inside an org. Super admins with no org
            context don't have department assignments — the row is pure noise. */}
        {!(isSuperAdmin && !org) && (
          <Row label="Departments">
            {myDepts.length === 0
              ? <span style={{ color: 'var(--ink-muted)' }}>None assigned</span>
              : myDepts.map((d) => <span key={d.id} className="cap-tag" style={{ marginRight: 4 }}>{d.name}</span>)}
          </Row>
        )}
      </div>

      <SectionHeading sub="Switch the interface colour scheme. Applies immediately across all pages.">
        Appearance
      </SectionHeading>
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '4px 18px' }}>
        <Row label="Theme"><ThemeSwitcher /></Row>
      </div>

      {/* Organisation section — hidden entirely for platform-level super admin
          (no org selected). They manage orgs from Platform → Organizations
          instead; the empty placeholder here just looked confusing. */}
      {!(isSuperAdmin && !org) && (
        <>
          <SectionHeading sub={isOrgAdmin ? 'You can change the organisation name. Slug stays fixed.' : 'Read-only — contact your org admin to change these.'}>
            Organisation
          </SectionHeading>
          {org ? (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '4px 18px' }}>
              <Row label="Logo">
                <OrgLogoEditor
                  org={org}
                  editable={isOrgAdmin}
                  onSaved={async () => { await loadOrg(); await refresh(); }}
                />
              </Row>
              <Row label="Name">
                {isOrgAdmin ? <OrgNameEditor org={org} onSaved={async () => { await loadOrg(); await refresh(); }} /> : org.name}
              </Row>
              <Row label="Slug">
                <span className="mono">{org.slug}</span>
              </Row>
              <Row label="Status">
                <span className={`cap-tag ${org.is_active ? 'cap-tag--accent' : ''}`}>
                  {org.is_active ? 'Active' : 'Suspended'}
                </span>
              </Row>
            </div>
          ) : (
            <div style={{ color: 'var(--ink-muted)', fontSize: 13 }}>
              No organisation assigned.
            </div>
          )}
        </>
      )}

    </AppShell>
  );
}
