import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AppShell from '../../components/AppShell.jsx';
import InviteLinkModal from '../../components/InviteLinkModal.jsx';
import { api, setOrgId } from '../../lib/api.js';
import { useAuth } from '../../lib/auth.jsx';


function Tile({ label, value, sub }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="tile-meta"><span>{sub}</span></div>}
    </div>
  );
}


function CreateOrgForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    name: '', slug: '', logo_url: '', admin_email: '', admin_name: '', admin_password: '',
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const update = (field) => (e) => setForm({ ...form, [field]: e.target.value });

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const payload = { ...form, logo_url: form.logo_url.trim() || null };
      const org = await api('/platform/orgs', { method: 'POST', body: payload });
      setForm({ name: '', slug: '', logo_url: '', admin_email: '', admin_name: '', admin_password: '' });
      setOpen(false);
      if (onCreated) onCreated(org);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="btn btn-primary" onClick={() => setOpen(true)}>
        + Create Organization
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="platform-form">
      <div className="platform-form-head">
        <h3 style={{ fontSize: 14, margin: 0, color: 'var(--ink)' }}>Create a new organization</h3>
        <button type="button" className="link-btn" onClick={() => setOpen(false)}>Cancel</button>
      </div>
      <div className="platform-form-grid">
        <label>
          <span>Org name</span>
          <input required value={form.name} onChange={update('name')} placeholder="Acme Pharma" />
        </label>
        <label>
          <span>Slug (lowercase, URL-safe)</span>
          <input required value={form.slug} onChange={update('slug')} placeholder="acme-pharma" pattern="[a-z0-9_-]+" />
        </label>
        <label>
          <span>Admin name</span>
          <input required value={form.admin_name} onChange={update('admin_name')} placeholder="Jane Doe" />
        </label>
        <label>
          <span>Admin email</span>
          <input required type="email" value={form.admin_email} onChange={update('admin_email')} placeholder="admin@example.com" />
        </label>
        <label style={{ gridColumn: '1 / -1' }}>
          <span>Admin password</span>
          <input required type="password" value={form.admin_password} onChange={update('admin_password')} placeholder="Min 8 characters" />
        </label>
        <label style={{ gridColumn: '1 / -1' }}>
          <span>Logo URL (optional)</span>
          <input
            type="url"
            value={form.logo_url}
            onChange={update('logo_url')}
            placeholder="https://…/logo.png"
            style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
          />
        </label>
      </div>
      {err && <div className="inv-warning" style={{ marginTop: 10 }}>{err}</div>}
      <div className="platform-form-footer">
        <div className="form-help">
          Creates the org, seeds 10 default departments, provisions the full agent catalog, and makes this user the ORG_ADMIN.
        </div>
        <button className="btn btn-primary" disabled={busy}>
          {busy ? 'Creating…' : 'Create organization'}
        </button>
      </div>
    </form>
  );
}


export default function PlatformOrgsPage() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [orgs, setOrgs] = useState([]);
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [o, s] = await Promise.all([
        api('/platform/orgs'),
        api('/platform/stats', { method: 'POST' }),
      ]);
      setOrgs(o);
      setStats(s);
      setErr('');
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  async function switchToOrg(orgId) {
    // As super_admin, get_org_context() accepts any org id. We set the
    // X-Org-Id header locally, flag the session so the sidebar switches into
    // admin mode for this tenant, then drop the super admin straight into the
    // org's admin dashboard — that's where they have the most leverage
    // (members, departments, integrations, agent installs).
    setOrgId(orgId);
    sessionStorage.setItem('sah.asOrg', String(orgId));
    if (refresh) await refresh();
    navigate('/admin/dashboard');
  }

  // Invite-an-org-admin flow. Super admin fills name + email, we POST to
  // /platform/invites and show the link in a modal for manual sharing.
  const [inviting, setInviting] = useState(null);   // { org_id, org_name }
  const [inviteForm, setInviteForm] = useState({ email: '', name: '' });
  const [inviteBusy, setInviteBusy] = useState(false);
  const [inviteErr, setInviteErr] = useState('');
  const [justCreated, setJustCreated] = useState(null);

  async function submitInvite(e) {
    e.preventDefault();
    setInviteBusy(true);
    setInviteErr('');
    try {
      const invite = await api('/platform/invites', {
        method: 'POST',
        body: {
          email: inviteForm.email,
          name: inviteForm.name,
          role: 'ORG_ADMIN',
          org_id: inviting.org_id,
        },
      });
      setInviteForm({ email: '', name: '' });
      setInviting(null);
      setJustCreated(invite);
    } catch (e2) {
      setInviteErr(e2.message);
    } finally {
      setInviteBusy(false);
    }
  }

  return (
    <AppShell crumbs={['Platform', 'Organizations']}>
      <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start', marginBottom: 22 }}>
        <div style={{ flex: 1 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            Platform <em>organizations</em>
          </h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            Every tenant on the platform. Super-admin only. Signed in as <b>{user?.name}</b>.
          </p>
        </div>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}

      {stats && (
        <div className="tiles">
          <Tile label="Organizations" value={stats.orgs} sub={`${stats.active_orgs} active`} />
          <Tile label="Users" value={stats.users} sub={`${stats.super_admins} super admins`} />
          <Tile label="Memberships" value={stats.memberships} sub="user-org links" />
          <Tile label="Agents provisioned" value={stats.agents} sub="across all orgs" />
          <Tile label="Total runs" value={stats.runs} sub="lifetime agent executions" />
        </div>
      )}

      <div style={{ marginBottom: 22 }}>
        <CreateOrgForm onCreated={() => loadAll()} />
      </div>

      <div className="section-header">
        <h2>Organizations <em>— {orgs.length}</em></h2>
      </div>

      {loading ? (
        <div className="empty">Loading…</div>
      ) : orgs.length === 0 ? (
        <div className="empty">No organizations yet. Use the button above to create the first one.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Slug</th>
              <th>Status</th>
              <th style={{ textAlign: 'right' }}>Members</th>
              <th style={{ textAlign: 'right' }}>Agents</th>
              <th style={{ textAlign: 'right' }}>Runs</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {orgs.map((o) => (
              <tr key={o.id}>
                <td style={{ color: 'var(--ink)', fontWeight: 500 }}>{o.name}</td>
                <td className="mono" style={{ color: 'var(--ink-dim)' }}>{o.slug}</td>
                <td>
                  <span className={`cap-tag ${o.is_active ? 'cap-tag--accent' : ''}`}>
                    {o.is_active ? 'Active' : 'Suspended'}
                  </span>
                </td>
                <td className="mono" style={{ textAlign: 'right' }}>{o.members}</td>
                <td className="mono" style={{ textAlign: 'right' }}>{o.agents}</td>
                <td className="mono" style={{ textAlign: 'right' }}>{o.runs}</td>
                <td style={{ textAlign: 'right' }}>
                  {/* M34: primary action "Invite admin" uses btn-primary for
                      parity with "+ Invite member" on the admin Members page.
                      "Open →" stays tertiary nav (link-btn). */}
                  <button
                    className="btn btn-primary"
                    onClick={() => setInviting({ org_id: o.id, org_name: o.name })}
                  >
                    + Invite admin
                  </button>
                  {' '}
                  <button className="link-btn" onClick={() => switchToOrg(o.id)}>
                    Open →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* Invite-admin modal */}
      {inviting && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
          display: 'grid', placeItems: 'center', zIndex: 100,
        }}>
          <form
            onSubmit={submitInvite}
            style={{
              width: 480, maxWidth: 'calc(100vw - 32px)',
              background: 'var(--bg-elev)', border: '1px solid var(--border-strong)',
              borderRadius: 12, padding: 24,
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
              <div>
                <h2 style={{ fontSize: 18, fontWeight: 500, marginBottom: 4 }}>
                  Invite an admin for {inviting.org_name}
                </h2>
                <p style={{ fontSize: 13, color: 'var(--ink-dim)', margin: 0 }}>
                  They'll be added as <b style={{ color: 'var(--accent)' }}>ORG_ADMIN</b> once they accept.
                </p>
              </div>
              {/* M34: modal dismissal uses neutral .btn (secondary action)
                  rather than .link-btn, matching IntegrationsPage + the shared
                  ConfirmDialog footer pattern. */}
              <button type="button" className="btn" onClick={() => setInviting(null)}>Cancel</button>
            </div>

            <div className="platform-form-grid">
              <label>
                <span>Name</span>
                <input
                  required
                  value={inviteForm.name}
                  onChange={(e) => setInviteForm({ ...inviteForm, name: e.target.value })}
                  placeholder="Jane Doe"
                />
              </label>
              <label>
                <span>Email</span>
                <input
                  required type="email"
                  value={inviteForm.email}
                  onChange={(e) => setInviteForm({ ...inviteForm, email: e.target.value })}
                  placeholder="admin@company.com"
                />
              </label>
            </div>

            {inviteErr && <div className="inv-warning" style={{ marginTop: 10 }}>{inviteErr}</div>}

            <div className="platform-form-footer">
              <div className="form-help">
                Creates a one-time sign-up link for this address.
              </div>
              <button type="submit" className="btn btn-primary" disabled={inviteBusy}>
                {inviteBusy ? 'Creating…' : 'Create invite'}
              </button>
            </div>
          </form>
        </div>
      )}

      {justCreated && (
        <InviteLinkModal invite={justCreated} onClose={() => setJustCreated(null)} />
      )}
    </AppShell>
  );
}
