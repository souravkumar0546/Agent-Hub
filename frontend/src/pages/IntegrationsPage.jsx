import { useCallback, useEffect, useMemo, useState } from 'react';
import AgentIcon from '../components/AgentIcon.jsx';
import AppShell from '../components/AppShell.jsx';
import { useConfirm, useToast } from '../components/Dialog.jsx';
import { api } from '../lib/api.js';

/**
 * Integrations — connections to external systems (ERP, HCM, SSO, comms).
 * Layout mirrors the product prototype: header stats, connected grid,
 * category filter, catalog grid.
 */


// Ordered category buckets for the filter chips. Values match what the
// catalog handler reports in `entry.category`.
const CATEGORY_ORDER = [
  'Enterprise Resource Planning',
  'Human Capital Management',
  'Identity & SSO',
  'Clinical & Regulatory',
  'Communication',
  'Document Management',
  'Data Warehouse',
  'Generic Webhook',
  'Other',
];


/* ── Helpers ────────────────────────────────────────────────────────── */

function formatRelTime(iso) {
  if (!iso) return null;
  const diff = Date.now() - new Date(iso).getTime();
  if (Number.isNaN(diff) || diff < 0) return null;
  const s = Math.round(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.round(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.round(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.round(h / 24);
  return `${d}d ago`;
}


function StatusBadge({ status }) {
  const map = {
    connected:    { label: 'Connected',    cls: 'int-status--ok' },
    disconnected: { label: 'Disconnected', cls: 'int-status--muted' },
    error:        { label: 'Error',        cls: 'int-status--err' },
  };
  const s = map[status] || map.disconnected;
  return (
    <span className={`int-status ${s.cls}`}>
      <span className="int-status-dot" />
      {s.label}
    </span>
  );
}


/* ── Connected card ─────────────────────────────────────────────────── */

function ConnectedCard({ integration, index, onTest, onEdit, onDelete, busyId }) {
  const disp = integration.display || {};
  const busy = busyId === integration.id;
  const corner = `INT-${String(index + 1).padStart(2, '0')}`;

  return (
    <article className="int-card">
      <span className="int-card-corner">{corner}</span>

      <div className="int-card-head">
        <div className={`int-card-logo int-card-logo--${disp.icon || 'plug'}`}>
          <AgentIcon name={disp.icon || 'plug'} size={22} />
        </div>
        <div className="int-card-meta">
          <div className="int-card-category">{disp.category || 'Integration'}</div>
          <div className="int-card-name">{integration.name}</div>
          <div className="int-card-vendor">{disp.name}</div>
        </div>
        <StatusBadge status={integration.status} />
      </div>

      <p className="int-card-desc">{disp.description}</p>

      <div className="int-card-stats">
        <div className="int-stat">
          <div className="int-stat-label">Credentials</div>
          <div className="int-stat-value">
            {integration.has_credentials ? '●●●●●●' : '—'}
          </div>
          <div className="int-stat-sub">
            {integration.credential_keys?.length
              ? integration.credential_keys.join(' · ')
              : 'Not set'}
          </div>
        </div>
        <div className="int-stat">
          <div className="int-stat-label">Last tested</div>
          <div className="int-stat-value">
            {formatRelTime(integration.last_tested_at) || '—'}
          </div>
          <div className="int-stat-sub">
            {integration.last_tested_at
              ? new Date(integration.last_tested_at).toLocaleDateString()
              : 'Never run'}
          </div>
        </div>
      </div>

      {integration.last_error && (
        <div className="int-card-err" title={integration.last_error}>
          {integration.last_error.slice(0, 220)}
          {integration.last_error.length > 220 ? '…' : ''}
        </div>
      )}

      <div className="int-card-actions">
        <button
          className="btn btn-primary"
          onClick={() => onTest(integration)}
          disabled={busy || !disp.implemented}
        >
          {busy ? 'Testing…' : 'Test connection'}
        </button>
        <button className="btn" onClick={() => onEdit(integration)} disabled={busy}>
          Configure
        </button>
        <button className="btn btn-danger" onClick={() => onDelete(integration)} disabled={busy}>
          Disconnect
        </button>
      </div>
    </article>
  );
}


/* ── Catalog tile ───────────────────────────────────────────────────── */

function ConnectorTile({ entry, onConnect }) {
  const klass = `connector-card ${!entry.implemented ? 'connector-card--soon' : ''}`;
  return (
    <article className={klass} onClick={() => entry.implemented && onConnect(entry)}>
      <div className="connector-head">
        <div className={`connector-logo connector-logo--${entry.icon || 'plug'}`}>
          <AgentIcon name={entry.icon || 'plug'} size={18} />
        </div>
        <div className="connector-body">
          <h4>{entry.name}</h4>
          <div className="connector-type">{entry.category}</div>
        </div>
      </div>
      <div className="connector-desc">{entry.description}</div>
      <div className="connector-footer">
        <span className="connector-badge">
          {entry.implemented ? 'Ready' : 'Coming soon'}
        </span>
        {entry.implemented ? (
          <span className="connector-cta">Connect →</span>
        ) : (
          <span className="connector-cta connector-cta--muted">—</span>
        )}
      </div>
    </article>
  );
}


/* ── Connect / edit modal ───────────────────────────────────────────── */

function ConnectModal({ mode, entry, integration, onClose, onSaved }) {
  const fields = entry?.fields || [];
  const configFields = fields.filter((f) => f.group === 'config');
  const credFields = fields.filter((f) => f.group === 'credentials');

  const [name, setName] = useState(integration?.name || entry?.name || '');
  const [config, setConfig] = useState(() => {
    const init = {};
    for (const f of configFields) {
      const existing = integration?.config?.[f.key];
      // Select fields fall back to their declared default so a fresh form
      // doesn't post an empty string the backend will reject.
      const fallback = f.type === 'select' ? (f.default || '') : '';
      init[f.key] = existing ?? fallback;
    }
    return init;
  });
  const [credentials, setCredentials] = useState(() => {
    const init = {};
    for (const f of credFields) {
      init[f.key] = f.type === 'select' ? (f.default || '') : '';
    }
    return init;
  });
  const [replaceCreds, setReplaceCreds] = useState(mode === 'create');
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  async function submit() {
    setErr('');
    for (const f of configFields) {
      if (f.required && !(config[f.key] || '').toString().trim()) {
        setErr(`${f.label} is required`); return;
      }
    }
    if (mode === 'create') {
      for (const f of credFields) {
        if (f.required && !(credentials[f.key] || '').toString().trim()) {
          setErr(`${f.label} is required`); return;
        }
      }
    }

    setSubmitting(true);
    try {
      let result;
      if (mode === 'create') {
        result = await api('/integrations', {
          method: 'POST',
          body: { type: entry.type, name: name.trim() || entry.name, config, credentials },
        });
      } else {
        const body = { name: name.trim() || integration.name, config };
        if (replaceCreds) body.credentials = credentials;
        result = await api(`/integrations/${integration.id}`, { method: 'PATCH', body });
      }
      onSaved(result);
    } catch (e) {
      setErr(e.message || 'Failed');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <div>
            <div className="modal-title">{mode === 'create' ? 'Connect' : 'Configure'} · {entry?.name}</div>
            <div className="modal-sub">{entry?.description}</div>
          </div>
          <button className="modal-close" onClick={onClose} aria-label="Close">×</button>
        </div>

        <div className="modal-body">
          <div className="form-row">
            <label className="form-label">Display name</label>
            <input
              type="text" className="form-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={entry?.name}
            />
            <div className="form-help">How this connection appears in the list. Defaults to the type name.</div>
          </div>

          {configFields.length > 0 && (
            <>
              <div className="form-section">Configuration</div>
              {configFields.map((f) => (
                <div key={f.key} className="form-row">
                  <label className="form-label">
                    {f.label}{f.required && <span className="form-req"> *</span>}
                  </label>
                  {f.type === 'textarea' ? (
                    <textarea className="form-input" rows={3} placeholder={f.placeholder || ''}
                      value={config[f.key] || ''}
                      onChange={(e) => setConfig({ ...config, [f.key]: e.target.value })} />
                  ) : f.type === 'select' ? (
                    <select className="form-input"
                      value={config[f.key] || ''}
                      onChange={(e) => setConfig({ ...config, [f.key]: e.target.value })}>
                      {(f.options || []).map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : (
                    <input type={f.type === 'password' ? 'password' : 'text'}
                      className="form-input" placeholder={f.placeholder || ''}
                      value={config[f.key] || ''}
                      onChange={(e) => setConfig({ ...config, [f.key]: e.target.value })} />
                  )}
                  {f.help && <div className="form-help">{f.help}</div>}
                </div>
              ))}
            </>
          )}

          {credFields.length > 0 && (
            <>
              <div className="form-section">
                Credentials
                {mode === 'edit' && !replaceCreds && (
                  <button className="link-btn" onClick={() => setReplaceCreds(true)} type="button"
                    style={{ marginLeft: 10, fontSize: 11 }}>
                    Replace
                  </button>
                )}
              </div>
              {mode === 'edit' && !replaceCreds ? (
                <div className="form-help" style={{
                  padding: '10px 12px', background: 'var(--bg-card)',
                  border: '1px solid var(--border)', borderRadius: 4,
                }}>
                  Existing credentials kept. Click <b>Replace</b> to rotate them.
                </div>
              ) : credFields.map((f) => (
                <div key={f.key} className="form-row">
                  <label className="form-label">
                    {f.label}{f.required && mode === 'create' && <span className="form-req"> *</span>}
                  </label>
                  {f.type === 'select' ? (
                    <select className="form-input"
                      value={credentials[f.key] || ''}
                      onChange={(e) => setCredentials({ ...credentials, [f.key]: e.target.value })}>
                      {(f.options || []).map((opt) => (
                        <option key={opt} value={opt}>{opt}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      type={f.type === 'password' ? 'password' : 'text'}
                      className="form-input" placeholder={f.placeholder || ''}
                      value={credentials[f.key] || ''}
                      autoComplete="new-password"
                      onChange={(e) => setCredentials({ ...credentials, [f.key]: e.target.value })}
                    />
                  )}
                  {f.help && <div className="form-help">{f.help}</div>}
                </div>
              ))}
            </>
          )}

          {err && <div className="inv-warning">{err}</div>}
        </div>

        <div className="modal-actions">
          <button className="btn" onClick={onClose} disabled={submitting}>Cancel</button>
          <button className="btn btn-primary" onClick={submit} disabled={submitting}>
            {submitting ? 'Saving…' : (mode === 'create' ? 'Connect' : 'Save')}
          </button>
        </div>
      </div>
    </div>
  );
}


/* ── Page ───────────────────────────────────────────────────────────── */

export default function IntegrationsPage() {
  const [catalog, setCatalog] = useState([]);
  const [connected, setConnected] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [modal, setModal] = useState(null);
  const [busyId, setBusyId] = useState(null);
  const [activeCat, setActiveCat] = useState('all');
  // Global dialog hooks — replaced the previous inline toast state + native
  // window.confirm (H26). Variant defaults to 'info'; pass 'error' for
  // failures, 'success' for positive confirmations.
  const confirm = useConfirm();
  const toast = useToast();

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      const [cat, list] = await Promise.all([
        api('/integrations/catalog'),
        api('/integrations'),
      ]);
      setCatalog(cat);
      setConnected(list);
      setErr('');
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);
  useEffect(() => { loadAll(); }, [loadAll]);


  async function onTest(integration) {
    setBusyId(integration.id);
    try {
      const result = await api(`/integrations/${integration.id}/test`, { method: 'POST' });
      setConnected((prev) => prev.map((i) => (i.id === integration.id ? result.integration : i)));
      if (result.ok) {
        toast(`Connected to ${integration.name}.`, { variant: 'success' });
      } else {
        toast(`Test failed: ${result.error}`, { variant: 'error' });
      }
    } catch (e) {
      toast(`Test failed: ${e.message}`, { variant: 'error' });
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(integration) {
    const ok = await confirm({
      title: `Disconnect ${integration.name}?`,
      message: 'Saved configuration and credentials are removed. This cannot be undone.',
      confirmLabel: 'Disconnect',
      destructive: true,
    });
    if (!ok) return;
    setBusyId(integration.id);
    try {
      await api(`/integrations/${integration.id}`, { method: 'DELETE' });
      setConnected((prev) => prev.filter((i) => i.id !== integration.id));
      toast('Disconnected.', { variant: 'success' });
    } catch (e) {
      toast(`Disconnect failed: ${e.message}`, { variant: 'error' });
    } finally {
      setBusyId(null);
    }
  }

  function onEdit(integration) {
    const entry = catalog.find((c) => c.type === integration.type);
    setModal({ mode: 'edit', entry, integration });
  }

  function onConnect(entry) {
    if (!entry.implemented) {
      toast(`${entry.name} — coming soon.`);
      return;
    }
    setModal({ mode: 'create', entry, integration: null });
  }

  function onSaved(result) {
    setConnected((prev) => {
      const idx = prev.findIndex((i) => i.id === result.id);
      if (idx >= 0) { const next = [...prev]; next[idx] = result; return next; }
      return [...prev, result];
    });
    const wasCreate = modal?.mode === 'create';
    setModal(null);
    toast(wasCreate ? 'Integration connected.' : 'Integration updated.', { variant: 'success' });
  }

  const connectedTypes = useMemo(() => new Set(connected.map((i) => i.type)), [connected]);
  const available = useMemo(
    () => catalog.filter((c) => !connectedTypes.has(c.type)),
    [catalog, connectedTypes],
  );

  const categories = useMemo(() => {
    const counts = new Map();
    for (const entry of available) {
      const k = entry.category || 'Other';
      counts.set(k, (counts.get(k) || 0) + 1);
    }
    const known = CATEGORY_ORDER.filter((k) => counts.has(k));
    const extra = Array.from(counts.keys())
      .filter((k) => !CATEGORY_ORDER.includes(k))
      .sort();
    return [...known, ...extra].map((k) => ({ key: k, count: counts.get(k) }));
  }, [available]);

  const shownCatalog = useMemo(() => {
    if (activeCat === 'all') return available;
    return available.filter((e) => (e.category || 'Other') === activeCat);
  }, [available, activeCat]);

  const stats = useMemo(() => {
    const total = connected.length;
    const ok = connected.filter((c) => c.status === 'connected').length;
    const needsAttention = connected.filter((c) => c.status !== 'connected').length;
    return { total, ok, needsAttention };
  }, [connected]);

  return (
    <AppShell crumbs={['Admin', 'Integrations']}>
      <section className="int-hero">
        <div className="int-hero-tag">
          ● {stats.total} active
          {stats.needsAttention > 0 && ` · ${stats.needsAttention} need attention`}
        </div>
        <h1 className="int-hero-title">
          Your <em>connected</em><br />systems of record.
        </h1>
        <p className="int-hero-sub">
          Wire agents into the enterprise stack — HCM, ERP, SSO, messaging.
          Credentials are encrypted at rest; every call is audit-logged.
        </p>

        <div className="int-hero-stats">
          <div>
            <div className="stat-label">Active connections</div>
            <div className="stat-value">{stats.total}</div>
          </div>
          <div>
            <div className="stat-label">Healthy</div>
            <div className="stat-value">{stats.ok}</div>
          </div>
          <div>
            <div className="stat-label">Need attention</div>
            <div className="stat-value">{stats.needsAttention}</div>
          </div>
          <div>
            <div className="stat-label">Catalog</div>
            <div className="stat-value">{catalog.length}</div>
          </div>
        </div>
      </section>

      {err && <div className="inv-warning" style={{ marginBottom: 16 }}>{err}</div>}
      {/* Toasts are rendered globally by <DialogProvider>. */}

      <div className="section-header">
        <h2>Active connections <em>— {connected.length}</em></h2>
      </div>
      {loading ? (
        <div className="empty">Loading…</div>
      ) : connected.length === 0 ? (
        <div className="empty">Nothing connected yet. Pick a connector below to start.</div>
      ) : (
        <div className="int-grid">
          {connected.map((i, idx) => (
            <ConnectedCard
              key={i.id}
              index={idx}
              integration={i}
              onTest={onTest}
              onEdit={onEdit}
              onDelete={onDelete}
              busyId={busyId}
            />
          ))}
        </div>
      )}

      <div className="section-header" style={{ marginTop: 36 }}>
        <h2>Add a connection <em>— {available.length} available</em></h2>
      </div>

      {categories.length > 0 && (
        <div className="cat-bar">
          <button
            type="button"
            className={`cat-chip${activeCat === 'all' ? ' active' : ''}`}
            onClick={() => setActiveCat('all')}
          >
            All<span className="cat-count">{available.length}</span>
          </button>
          {categories.map((c) => (
            <button
              key={c.key}
              type="button"
              className={`cat-chip${activeCat === c.key ? ' active' : ''}`}
              onClick={() => setActiveCat(c.key)}
            >
              {c.key}<span className="cat-count">{c.count}</span>
            </button>
          ))}
        </div>
      )}

      <div className="connector-grid">
        {shownCatalog.map((entry) => (
          <ConnectorTile key={entry.type} entry={entry} onConnect={onConnect} />
        ))}
      </div>

      {modal && (
        <ConnectModal
          mode={modal.mode}
          entry={modal.entry}
          integration={modal.integration}
          onClose={() => setModal(null)}
          onSaved={onSaved}
        />
      )}
    </AppShell>
  );
}
