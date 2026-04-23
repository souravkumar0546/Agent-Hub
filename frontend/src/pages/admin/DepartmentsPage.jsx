import { useCallback, useEffect, useState } from 'react';
import AppShell from '../../components/AppShell.jsx';
import { useConfirm, useToast } from '../../components/Dialog.jsx';
import { api } from '../../lib/api.js';
import { useAuth } from '../../lib/auth.jsx';


/** Inline "Create department" form — collapses back into a button when idle. */
function CreateDeptForm({ onCreated }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState('');
  const [slug, setSlug] = useState('');
  const [description, setDescription] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  function reset() {
    setName('');
    setSlug('');
    setDescription('');
    setErr('');
  }

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErr('');
    try {
      const finalSlug = (slug.trim() || name.trim())
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
      const created = await api('/departments', {
        method: 'POST',
        body: { name: name.trim(), slug: finalSlug, description: description.trim() || null },
      });
      reset();
      setOpen(false);
      if (onCreated) onCreated(created);
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button className="btn btn-primary" onClick={() => setOpen(true)}>
        + New department
      </button>
    );
  }

  return (
    <form onSubmit={submit} className="platform-form">
      <div className="platform-form-head">
        <h3 style={{ fontSize: 14, margin: 0, color: 'var(--ink)' }}>New department</h3>
        <button
          type="button"
          className="link-btn"
          onClick={() => { reset(); setOpen(false); }}
        >
          Cancel
        </button>
      </div>
      <div className="platform-form-grid">
        <label>
          <span>Name</span>
          <input
            required
            value={name}
            onChange={(e) => {
              setName(e.target.value);
              // Auto-suggest a slug from the name so admins don't have to think
              // about URL-safe casing; they can still override.
              setSlug(
                e.target.value
                  .toLowerCase()
                  .replace(/[^a-z0-9]+/g, '_')
                  .replace(/^_+|_+$/g, '')
              );
            }}
            placeholder="Finance Operations"
          />
        </label>
        <label>
          <span>Slug</span>
          <input
            required
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="finance_operations"
            pattern="[a-z0-9_-]+"
            style={{ fontFamily: 'var(--mono)', fontSize: 12 }}
          />
        </label>
        <label style={{ gridColumn: '1 / -1' }}>
          <span>Description (optional)</span>
          <input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Short description shown on hover"
          />
        </label>
      </div>
      {err && <div className="inv-warning" style={{ marginTop: 10 }}>{err}</div>}
      <div className="platform-form-footer">
        <div className="form-help">
          Departments control which members see which agents. You can scope agents to specific departments from the Agent Library.
        </div>
        <button className="btn btn-primary" disabled={busy || !name.trim()}>
          {busy ? 'Creating…' : 'Create department'}
        </button>
      </div>
    </form>
  );
}


export default function DepartmentsPage() {
  const { isOrgAdmin } = useAuth();
  const [depts, setDepts] = useState([]);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const confirm = useConfirm();
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const rows = await api('/departments');
      setDepts(rows);
      setErr('');
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  async function doDelete(d) {
    const ok = await confirm({
      title: `Delete "${d.name}"?`,
      message:
        'Members will remain in the org but lose this department tag. '
        + 'Agents scoped only to this department fall back to org-wide visibility.\n\n'
        + 'This cannot be undone.',
      confirmLabel: 'Delete department',
      destructive: true,
    });
    if (!ok) return;
    setPendingDeleteId(d.id);
    try {
      await api(`/departments/${d.id}`, { method: 'DELETE' });
      toast(`Department "${d.name}" deleted.`, { variant: 'success' });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setPendingDeleteId(null);
    }
  }

  return (
    <AppShell crumbs={['Admin', 'Departments']}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }}>
        <div>
          <h1 className="page-title" style={{ marginBottom: 4 }}>Departments</h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            Groupings that control which members see which agents.
          </p>
        </div>
        {isOrgAdmin && <CreateDeptForm onCreated={() => load()} />}
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}

      {loading ? (
        <div className="empty">Loading…</div>
      ) : depts.length === 0 ? (
        <div className="empty">
          No departments yet. {isOrgAdmin ? 'Use the button above to add one.' : 'Ask your org admin to create the first one.'}
        </div>
      ) : (
        <table className="table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Slug</th>
              <th>Description</th>
              {isOrgAdmin && <th style={{ textAlign: 'right', width: 120 }}>Actions</th>}
            </tr>
          </thead>
          <tbody>
            {depts.map((d) => (
              <tr key={d.id}>
                <td style={{ color: 'var(--ink)', fontWeight: 500 }}>{d.name}</td>
                <td style={{ color: 'var(--ink-dim)', fontFamily: 'var(--mono)', fontSize: 12 }}>{d.slug}</td>
                <td style={{ color: 'var(--ink-dim)' }}>{d.description || '—'}</td>
                {isOrgAdmin && (
                  <td style={{ textAlign: 'right' }}>
                    {/* M34: destructive actions use filled .btn-danger everywhere,
                        not link + inline red. Matches IntegrationsPage
                        "Disconnect". */}
                    <button
                      className="btn btn-danger"
                      onClick={() => doDelete(d)}
                      disabled={pendingDeleteId === d.id}
                    >
                      {pendingDeleteId === d.id ? 'Deleting…' : 'Delete'}
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </AppShell>
  );
}
