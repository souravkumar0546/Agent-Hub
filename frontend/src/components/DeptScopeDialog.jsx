import { useEffect, useState } from 'react';
import { api } from '../lib/api.js';

/**
 * Department-scope picker dialog used on the Agent Library install / manage
 * actions. Admins tick which departments an agent should be visible to, and
 * can spin up a new department inline without leaving the flow.
 *
 * Props:
 *   title: string                        — dialog title
 *   subtitle?: string                    — explanatory sub-line
 *   initialDeptIds?: number[]            — pre-checked ids (edit mode)
 *   onCancel(): void
 *   onConfirm(selectedIds: number[]): Promise<void>
 *   confirmLabel?: string                — text on the primary button
 *   orgId?: number                       — optional: override X-Org-Id for the
 *                                          embedded /departments calls. Used by
 *                                          the platform super-admin matrix to
 *                                          target a specific tenant without
 *                                          swapping the user's localStorage org.
 */
export default function DeptScopeDialog({
  title,
  subtitle,
  initialDeptIds = [],
  onCancel,
  onConfirm,
  confirmLabel = 'Confirm',
  orgId,
}) {
  const [depts, setDepts] = useState([]);
  const [selected, setSelected] = useState(new Set(initialDeptIds));
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  // Inline create
  const [newName, setNewName] = useState('');
  const [newSlug, setNewSlug] = useState('');
  const [creating, setCreating] = useState(false);

  // If the caller supplied a target orgId (super-admin platform flow), force
  // every /departments request here to that tenant. Otherwise the helper falls
  // through to the session's active org.
  const orgHeaders = orgId ? { 'X-Org-Id': String(orgId) } : undefined;

  const loadDepts = async () => {
    setLoading(true);
    try {
      const list = await api('/departments', orgHeaders ? { headers: orgHeaders } : undefined);
      setDepts(list);
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { loadDepts(); }, [orgId]);

  function toggle(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  }

  async function createDept(e) {
    e.preventDefault();
    if (!newName.trim()) return;
    setCreating(true);
    setErr('');
    try {
      const slug = (newSlug.trim() || newName.trim())
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '_')
        .replace(/^_+|_+$/g, '');
      const created = await api('/departments', {
        method: 'POST',
        body: { name: newName.trim(), slug, description: null },
        ...(orgHeaders ? { headers: orgHeaders } : {}),
      });
      // Reload the list and auto-select the new one.
      await loadDepts();
      setSelected((prev) => new Set(prev).add(created.id));
      setNewName('');
      setNewSlug('');
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setCreating(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setErr('');
    try {
      await onConfirm(Array.from(selected));
    } catch (e2) {
      setErr(e2.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.55)',
      display: 'grid', placeItems: 'center', zIndex: 100,
    }}>
      <div style={{
        width: 560, maxWidth: 'calc(100vw - 32px)',
        background: 'var(--bg-elev)', border: '1px solid var(--border-strong)',
        borderRadius: 12, padding: 24,
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 14 }}>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 500, marginBottom: 4 }}>{title}</h2>
            {subtitle && <p style={{ fontSize: 13, color: 'var(--ink-dim)', margin: 0 }}>{subtitle}</p>}
          </div>
          <button type="button" className="link-btn" onClick={onCancel}>Cancel</button>
        </div>

        <div style={{ fontSize: 11, color: 'var(--ink-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
          Available departments
        </div>

        {loading ? (
          <div style={{ fontSize: 12, color: 'var(--ink-muted)', padding: '12px 0' }}>Loading…</div>
        ) : depts.length === 0 ? (
          <div style={{ fontSize: 12, color: 'var(--ink-muted)', padding: '12px 0' }}>
            No departments yet. Create one below to get started.
          </div>
        ) : (
          <div className="filter-row" style={{ marginBottom: 10 }}>
            {depts.map((d) => (
              <button
                key={d.id}
                type="button"
                className={`filter-chip${selected.has(d.id) ? ' active' : ''}`}
                onClick={() => toggle(d.id)}
              >
                {d.name}
              </button>
            ))}
          </div>
        )}

        <div style={{
          fontSize: 12, color: 'var(--ink-muted)', marginTop: 4,
          padding: 10, background: 'rgba(107, 179, 242, 0.06)',
          border: '1px solid rgba(107, 179, 242, 0.18)',
          borderRadius: 6, lineHeight: 1.5,
        }}>
          {selected.size === 0
            ? 'No departments selected — the agent will be visible to every member of the org.'
            : `Selected ${selected.size} department${selected.size === 1 ? '' : 's'}. Members outside these departments won't see this agent in their workspace.`}
        </div>

        {/* Inline create */}
        <form onSubmit={createDept} style={{
          marginTop: 18, paddingTop: 14,
          borderTop: '1px solid var(--border)',
        }}>
          <div style={{ fontSize: 11, color: 'var(--ink-muted)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 8 }}>
            Or create a new department
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'stretch' }}>
            <input
              value={newName}
              onChange={(e) => {
                setNewName(e.target.value);
                // Auto-populate slug suggestion from name.
                setNewSlug(
                  e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
                );
              }}
              placeholder="Department name (e.g. Finance Ops)"
              style={{
                flex: 1, background: 'var(--bg)', border: '1px solid var(--border)',
                color: 'var(--ink)', padding: '8px 10px', borderRadius: 4, fontSize: 13, outline: 'none',
              }}
            />
            <input
              value={newSlug}
              onChange={(e) => setNewSlug(e.target.value)}
              placeholder="slug"
              pattern="[a-z0-9_-]+"
              style={{
                width: 140, background: 'var(--bg)', border: '1px solid var(--border)',
                color: 'var(--ink)', padding: '8px 10px', borderRadius: 4, fontSize: 12,
                fontFamily: 'var(--mono)', outline: 'none',
              }}
            />
            <button type="submit" className="btn" disabled={creating || !newName.trim()}>
              {creating ? 'Creating…' : '+ Create'}
            </button>
          </div>
        </form>

        {err && <div className="inv-warning" style={{ marginTop: 14 }}>{err}</div>}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginTop: 18 }}>
          <button type="button" className="btn" onClick={onCancel} disabled={busy}>Cancel</button>
          <button type="button" className="btn btn-primary" onClick={confirm} disabled={busy}>
            {busy ? 'Saving…' : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
