import { useEffect, useState } from 'react';
import AppShell from '../../components/AppShell.jsx';
import { LoadingBlock } from '../../components/Loading.jsx';
import { api } from '../../lib/api.js';

export default function AuditLogPage() {
  const [rows, setRows] = useState([]);
  const [err, setErr] = useState('');
  // M39: previously no loading state at all — the empty table silently
  // pretended "no events yet" during the fetch. Now we distinguish loading /
  // error / empty / populated explicitly.
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api('/audit')
      .then((data) => { if (!cancelled) setRows(data); })
      .catch((e) => { if (!cancelled) setErr(e.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  return (
    <AppShell crumbs={['Admin', 'Audit Log']}>
      <h1 className="page-title">Audit Log</h1>
      <p className="page-subtitle">Every notable action in this organization, with full lineage.</p>
      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}
      {loading ? (
        <LoadingBlock text="Loading audit events…" />
      ) : (
        <div style={{ overflowX: 'auto' }}>
          <table className="table">
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Target</th>
                <th>User</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td style={{ fontFamily: 'var(--mono)', fontSize: 12, color: 'var(--ink-dim)' }}>{r.created_at}</td>
                  <td>{r.action}</td>
                  <td style={{ color: 'var(--ink-dim)' }}>
                    {r.target_type ? `${r.target_type}${r.target_id ? `:${r.target_id}` : ''}` : '\u2014'}
                  </td>
                  <td style={{ color: 'var(--ink-dim)' }}>{r.user_id ?? '\u2014'}</td>
                </tr>
              ))}
              {rows.length === 0 && !err && (
                <tr>
                  <td colSpan={4} style={{ textAlign: 'center', padding: 32, color: 'var(--ink-dim)' }}>
                    No events yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
