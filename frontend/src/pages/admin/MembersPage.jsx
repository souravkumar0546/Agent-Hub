import { useCallback, useEffect, useState } from 'react';
import AppShell from '../../components/AppShell.jsx';
import { useConfirm, useToast } from '../../components/Dialog.jsx';
import InviteLinkModal from '../../components/InviteLinkModal.jsx';
import { api } from '../../lib/api.js';


function InviteForm({ departments, onInvited }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({ email: '', name: '', role: 'MEMBER', department_ids: [] });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  function toggleDept(id) {
    setForm((f) => ({
      ...f,
      department_ids: f.department_ids.includes(id)
        ? f.department_ids.filter((x) => x !== id)
        : [...f.department_ids, id],
    }));
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const invite = await api('/members/invites', { method: 'POST', body: form });
      setForm({ email: '', name: '', role: 'MEMBER', department_ids: [] });
      setOpen(false);
      if (onInvited) onInvited(invite);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return <button className="btn btn-primary" onClick={() => setOpen(true)}>+ Invite member</button>;
  }

  return (
    <form onSubmit={submit} className="platform-form">
      <div className="platform-form-head">
        <h3 style={{ fontSize: 14, margin: 0, color: 'var(--ink)' }}>Send an invitation</h3>
        <button type="button" className="link-btn" onClick={() => setOpen(false)}>Cancel</button>
      </div>

      <div className="platform-form-grid">
        <label>
          <span>Name</span>
          <input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Jane Doe" />
        </label>
        <label>
          <span>Email</span>
          <input required type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="jane@company.com" />
        </label>
        <label>
          <span>Role</span>
          <select
            value={form.role}
            onChange={(e) => setForm({ ...form, role: e.target.value })}
            style={{
              background: 'var(--bg)', border: '1px solid var(--border)',
              color: 'var(--ink)', padding: '8px 10px', borderRadius: 'var(--radius)',
              fontSize: 13, textTransform: 'none', letterSpacing: 'normal',
            }}
          >
            <option value="MEMBER">Member</option>
            <option value="ORG_ADMIN">Org Admin</option>
          </select>
        </label>
      </div>

      {departments.length > 0 && (
        <div style={{ marginTop: 14 }}>
          <div style={{ fontSize: 11, color: 'var(--ink-muted)', letterSpacing: '0.04em', textTransform: 'uppercase', marginBottom: 6 }}>
            Departments (optional)
          </div>
          <div className="filter-row">
            {departments.map((d) => (
              <button
                key={d.id}
                type="button"
                className={`filter-chip${form.department_ids.includes(d.id) ? ' active' : ''}`}
                onClick={() => toggleDept(d.id)}
              >
                {d.name}
              </button>
            ))}
          </div>
        </div>
      )}

      {err && <div className="inv-warning" style={{ marginTop: 10 }}>{err}</div>}
      <div className="platform-form-footer">
        <div className="form-help">
          Creates a sign-up link for this address.
        </div>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Creating…' : 'Create invite'}</button>
      </div>
    </form>
  );
}


function InviteBadge({ status }) {
  const color = status === 'pending' ? 'var(--warn)'
    : status === 'accepted' ? 'var(--accent)'
    : 'var(--err)';
  return <span className="cap-tag" style={{ color, borderColor: color }}>{status}</span>;
}


function inviteStatus(i) {
  if (i.accepted_at) return 'accepted';
  if (i.revoked_at) return 'revoked';
  if (i.expires_at && new Date(i.expires_at) < new Date()) return 'expired';
  return 'pending';
}


export default function MembersPage() {
  const [members, setMembers] = useState([]);
  const [invites, setInvites] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [err, setErr] = useState('');
  const [justCreated, setJustCreated] = useState(null);
  const confirm = useConfirm();
  const toast = useToast();

  const load = useCallback(async () => {
    try {
      const [m, i, d] = await Promise.all([
        api('/members'),
        api('/members/invites'),
        api('/departments'),
      ]);
      setMembers(m);
      setInvites(i);
      setDepartments(d);
      setErr('');
    } catch (e) {
      setErr(e.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function revoke(inviteId) {
    const ok = await confirm({
      title: 'Revoke this invite?',
      message: 'The invite link will stop working. Anyone who hasn\u2019t accepted yet won\u2019t be able to use it.',
      confirmLabel: 'Revoke invite',
      destructive: true,
    });
    if (!ok) return;
    try {
      await api(`/invites/${inviteId}`, { method: 'DELETE' });
      toast('Invite revoked.', { variant: 'success' });
      await load();
    } catch (e) {
      toast(`Revoke failed: ${e.message}`, { variant: 'error' });
    }
  }

  return (
    <AppShell crumbs={['Admin', 'Members']}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
        <div>
          <h1 className="page-title">Members</h1>
          <p className="page-subtitle">Who has access to this organization and which departments they're in.</p>
        </div>
      </div>

      <div style={{ marginBottom: 20 }}>
        <InviteForm departments={departments} onInvited={(inv) => { setJustCreated(inv); load(); }} />
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}

      <div className="section-header">
        <h2>Active members <em>— {members.length}</em></h2>
      </div>
      <table className="table" style={{ marginBottom: 28 }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Role</th>
            <th>Departments</th>
          </tr>
        </thead>
        <tbody>
          {members.map((m) => (
            <tr key={m.user_id}>
              <td style={{ color: 'var(--ink)', fontWeight: 500 }}>{m.name}</td>
              <td style={{ color: 'var(--ink-dim)' }}>{m.email}</td>
              <td><span className="cap-tag cap-tag--accent">{m.role}</span></td>
              <td>
                {m.departments.length === 0
                  ? <span style={{ color: 'var(--ink-muted)' }}>—</span>
                  : m.departments.map((d) => (
                      <span key={d.id} className="cap-tag" style={{ marginRight: 4 }}>{d.name}</span>
                    ))}
              </td>
            </tr>
          ))}
          {members.length === 0 && (
            <tr><td colSpan={4} style={{ color: 'var(--ink-dim)', textAlign: 'center', padding: 32 }}>No members yet.</td></tr>
          )}
        </tbody>
      </table>

      <div className="section-header">
        <h2>Invitations <em>— {invites.length}</em></h2>
      </div>
      {invites.length === 0 ? (
        <div className="empty">No invitations sent yet.</div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Email</th>
              <th>Role</th>
              <th>Status</th>
              <th>Expires</th>
              <th style={{ textAlign: 'right' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {invites.map((i) => {
              const s = inviteStatus(i);
              return (
                <tr key={i.id}>
                  <td>{i.name}</td>
                  <td style={{ color: 'var(--ink-dim)' }}>{i.email}</td>
                  <td><span className="cap-tag">{i.role}</span></td>
                  <td><InviteBadge status={s} /></td>
                  <td className="mono" style={{ fontSize: 11 }}>
                    {i.expires_at ? new Date(i.expires_at).toLocaleDateString() : '—'}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    {s === 'pending' && (
                      <>
                        <button className="link-btn" onClick={() => setJustCreated(i)}>Copy link</button>
                        {' · '}
                        <button className="link-btn" onClick={() => revoke(i.id)}>Revoke</button>
                      </>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}

      {justCreated && (
        <InviteLinkModal invite={justCreated} onClose={() => setJustCreated(null)} />
      )}
    </AppShell>
  );
}
