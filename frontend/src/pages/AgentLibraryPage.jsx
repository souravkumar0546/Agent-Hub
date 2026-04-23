import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import AgentIcon from '../components/AgentIcon.jsx';
import AppShell from '../components/AppShell.jsx';
import DeptScopeDialog from '../components/DeptScopeDialog.jsx';
import { useConfirm, useToast } from '../components/Dialog.jsx';
import { api } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';


/** Card action button — text + handler depend on role + state. */
function ActionButton({
  entry, role, onInstall, onUninstall, onPick, onUnpick, onManageDepts, busy,
}) {
  const disabled = busy || !entry.implemented;

  if (!entry.implemented) {
    return <span className="cap-tag">Coming soon</span>;
  }

  if (role === 'admin') {
    if (entry.is_installed) {
      return (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <span className="cap-tag cap-tag--accent">Installed</span>
          <button className="link-btn" onClick={() => onManageDepts(entry)} disabled={disabled}>
            Departments
          </button>
          {' · '}
          <button className="link-btn" onClick={() => onUninstall(entry)} disabled={disabled}>
            Uninstall
          </button>
        </div>
      );
    }
    return (
      <button className="btn btn-primary" onClick={() => onInstall(entry)} disabled={disabled}>
        + Install to org
      </button>
    );
  }

  // Member
  if (!entry.is_installed) {
    return <span className="cap-tag">Not available in your org</span>;
  }
  if (entry.is_picked) {
    return (
      <div style={{ display: 'flex', gap: 6 }}>
        <span className="cap-tag cap-tag--accent">In your workspace</span>
        <button className="link-btn" onClick={() => onUnpick(entry)} disabled={disabled}>Remove</button>
      </div>
    );
  }
  return (
    <button className="btn btn-primary" onClick={() => onPick(entry)} disabled={disabled}>
      + Add to my workspace
    </button>
  );
}


export default function AgentLibraryPage() {
  const { isOrgAdmin } = useAuth();
  const navigate = useNavigate();
  const role = isOrgAdmin ? 'admin' : 'member';
  const confirm = useConfirm();
  const toast = useToast();

  const [catalog, setCatalog] = useState([]);
  const [err, setErr] = useState('');
  const [busy, setBusy] = useState(false);
  const [filter, setFilter] = useState('all'); // all | installed | missing | mine
  const [category, setCategory] = useState('');
  const [query, setQuery] = useState('');

  const load = useCallback(async () => {
    try {
      const rows = await api('/agents/catalog');
      setCatalog(rows);
      setErr('');
    } catch (e) {
      setErr(e.message);
    }
  }, []);
  useEffect(() => { load(); }, [load]);

  const categories = useMemo(() => {
    const seen = new Set();
    catalog.forEach((c) => { if (c.category) seen.add(c.category); });
    return Array.from(seen).sort();
  }, [catalog]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return catalog.filter((c) => {
      if (category && c.category !== category) return false;
      if (filter === 'installed' && !c.is_installed) return false;
      if (filter === 'missing' && c.is_installed) return false;
      if (filter === 'mine' && !c.is_picked) return false;
      if (q) {
        // Match against user-facing fields only — name, tagline, category,
        // and the stable `type` slug (so power users can type "rca_" etc.).
        // Search the short brand name (e.g. "Vera") alongside the long
        // name so either gets the agent — users search by whatever they
        // remember.
        const hay = `${c.display_name || ''} ${c.name} ${c.tagline || ''} ${c.category || ''} ${c.type}`.toLowerCase();
        if (!hay.includes(q)) return false;
      }
      return true;
    });
  }, [catalog, filter, category, query]);

  // Opens the dept-scope dialog before installing; admin can leave it empty
  // (= org-wide) or pick specific departments. We keep `pendingInstall` null
  // unless the dialog is open.
  const [pendingInstall, setPendingInstall] = useState(null);
  const [pendingManage, setPendingManage] = useState(null);
  function doInstall(entry) {
    setPendingInstall(entry);
  }
  async function confirmInstall(department_ids) {
    const entry = pendingInstall;
    setPendingInstall(null);
    setBusy(true);
    try {
      await api('/agents/install', {
        method: 'POST',
        body: { type: entry.type, department_ids },
      });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  // "Departments" action on an installed card — open the dialog pre-filled
  // with the agent's current dept ids and PATCH on confirm.
  async function doManageDepts(entry) {
    if (!entry.agent_id) return;
    // Need to look up current dept ids. The catalog endpoint doesn't include
    // them, so hit /agents?scope=all and find this one.
    try {
      const list = await api('/agents?scope=all');
      const full = list.find((a) => a.id === entry.agent_id);
      setPendingManage({
        entry,
        initialDeptIds: (full?.departments || []).map((d) => d.id),
      });
    } catch (e) {
      setErr(e.message);
    }
  }
  async function confirmManageDepts(department_ids) {
    const { entry } = pendingManage;
    setPendingManage(null);
    setBusy(true);
    try {
      await api(`/agents/${entry.agent_id}`, {
        method: 'PATCH',
        body: { department_ids },
      });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function doUninstall(entry) {
    if (!entry.agent_id) return;
    const niceName = entry.display_name || entry.name;
    const ok = await confirm({
      title: `Uninstall ${niceName}?`,
      message: 'Members will lose access until you reinstall.',
      confirmLabel: 'Uninstall',
      destructive: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await api(`/agents/${entry.agent_id}`, { method: 'PATCH', body: { is_enabled: false } });
      toast(`${niceName} uninstalled.`, { variant: 'success' });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function doPick(entry) {
    if (!entry.agent_id) return;
    setBusy(true);
    try {
      await api('/me/agents', { method: 'POST', body: { agent_id: entry.agent_id } });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function doUnpick(entry) {
    if (!entry.agent_id) return;
    setBusy(true);
    try {
      await api(`/me/agents/${entry.agent_id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell crumbs={['Agent Library']}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 18 }}>
        <div>
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            Agent <em>library</em>
          </h1>
          <p className="page-subtitle" style={{ marginBottom: 0 }}>
            {role === 'admin'
              ? 'Browse every agent on the platform. Install the ones your organisation needs.'
              : 'Browse the agents your organisation has enabled. Add the ones you need to your workspace.'}
          </p>
        </div>
        <button className="btn" onClick={() => navigate(-1)}>← Back</button>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}

      {/* Search bar — fuzzy-ish substring match against name / tagline /
          category / type slug. Sits above the filter chips so it's the first
          thing users reach for when they know what they want. */}
      <div style={{
        display: 'flex', gap: 10, alignItems: 'center',
        marginBottom: 12,
      }}>
        <div style={{ position: 'relative', flex: 1, maxWidth: 420 }}>
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.6"
            style={{
              position: 'absolute', top: '50%', left: 10,
              width: 16, height: 16, transform: 'translateY(-50%)',
              color: 'var(--ink-muted)', pointerEvents: 'none',
            }}
          >
            <circle cx="11" cy="11" r="7" />
            <path d="M20 20l-3.5-3.5" />
          </svg>
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search agents by name, tagline, category…"
            style={{
              width: '100%',
              background: 'var(--bg)',
              border: '1px solid var(--border)',
              color: 'var(--ink)',
              padding: '8px 32px 8px 32px',
              borderRadius: 999,
              fontSize: 13,
              outline: 'none',
            }}
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery('')}
              aria-label="Clear search"
              style={{
                position: 'absolute', top: '50%', right: 8,
                transform: 'translateY(-50%)',
                background: 'transparent', border: 0,
                color: 'var(--ink-muted)', fontSize: 16, lineHeight: 1,
                padding: '4px 6px', borderRadius: 999, cursor: 'pointer',
              }}
            >
              ×
            </button>
          )}
        </div>
        {query && (
          <span style={{ color: 'var(--ink-muted)', fontSize: 12 }}>
            {filtered.length} match{filtered.length === 1 ? '' : 'es'}
          </span>
        )}
      </div>

      <div className="filter-row">
        <button className={`filter-chip${filter === 'all' ? ' active' : ''}`} onClick={() => setFilter('all')}>All</button>
        {role === 'admin' ? (
          <>
            <button className={`filter-chip${filter === 'installed' ? ' active' : ''}`} onClick={() => setFilter('installed')}>Installed</button>
            <button className={`filter-chip${filter === 'missing' ? ' active' : ''}`} onClick={() => setFilter('missing')}>Not installed</button>
          </>
        ) : (
          <>
            <button className={`filter-chip${filter === 'installed' ? ' active' : ''}`} onClick={() => setFilter('installed')}>Available</button>
            <button className={`filter-chip${filter === 'mine' ? ' active' : ''}`} onClick={() => setFilter('mine')}>In my workspace</button>
          </>
        )}
        <span style={{ borderLeft: '1px solid var(--border)', margin: '0 6px' }} />
        <button className={`filter-chip${category === '' ? ' active' : ''}`} onClick={() => setCategory('')}>Any category</button>
        {categories.map((c) => (
          <button key={c} className={`filter-chip${category === c ? ' active' : ''}`} onClick={() => setCategory(c)}>{c}</button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="empty">Nothing matches that filter.</div>
      ) : (
        <div className="agent-grid">
          {filtered.map((entry) => (
            <div
              key={entry.type}
              className="agent-card"
              style={{
                cursor: 'default',
                opacity: entry.implemented ? 1 : 0.55,
              }}
            >
              <div className="agent-icon">
                <AgentIcon name={entry.icon || 'chart'} />
              </div>
              {/* Brand-style short name as the card headline; fall back to
                  the long name when there's no display_name yet (e.g. a
                  catalog entry that wasn't in the rename sweep). When both
                  exist we render the long name as a quiet subtitle so the
                  mapping "Devio = RCA / Investigation" stays legible. */}
              <div className="agent-name">{entry.display_name || entry.name}</div>
              {entry.display_name && entry.display_name !== entry.name && (
                <div className="agent-subname" title={entry.name}>{entry.name}</div>
              )}
              <div className="agent-tagline">{entry.tagline}</div>
              <div className="agent-meta">
                {entry.category && <span className="cap-tag cap-tag--accent">{entry.category}</span>}
                {!entry.implemented && <span className="cap-tag">Coming soon</span>}
              </div>
              <div style={{ marginTop: 4 }}>
                <ActionButton
                  entry={entry}
                  role={role}
                  onInstall={doInstall}
                  onUninstall={doUninstall}
                  onPick={doPick}
                  onUnpick={doUnpick}
                  onManageDepts={doManageDepts}
                  busy={busy}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {pendingInstall && (
        <DeptScopeDialog
          title={`Install ${pendingInstall.name}`}
          subtitle="Optionally restrict this agent to specific departments. Skip to install org-wide."
          initialDeptIds={[]}
          onCancel={() => setPendingInstall(null)}
          onConfirm={confirmInstall}
          confirmLabel="Install"
        />
      )}

      {pendingManage && (
        <DeptScopeDialog
          title={`Manage ${pendingManage.entry.name} departments`}
          subtitle="Pick which departments can see this agent. Members outside these depts will lose access."
          initialDeptIds={pendingManage.initialDeptIds}
          onCancel={() => setPendingManage(null)}
          onConfirm={confirmManageDepts}
          confirmLabel="Save departments"
        />
      )}
    </AppShell>
  );
}
