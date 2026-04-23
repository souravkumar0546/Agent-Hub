import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import AppShell from '../components/AppShell.jsx';
import { LoadingBlock } from '../components/Loading.jsx';
import { api } from '../lib/api.js';
import { useBrand } from '../lib/brand.js';
import { useThemeColors } from '../lib/useThemeColors.js';


function Tile({ label, value, sub }) {
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value">{value}</div>
      {sub && <div className="tile-meta"><span>{sub}</span></div>}
    </div>
  );
}


function ChartCard({ title, sub, children }) {
  return (
    <div className="chart-card">
      <div className="chart-card-head">
        <div>
          <div className="chart-card-title">{title}</div>
          {sub && <div className="chart-card-sub">{sub}</div>}
        </div>
      </div>
      <div className="chart-card-body">{children}</div>
    </div>
  );
}


function statusColor(status) {
  if (status === 'connected') return 'var(--accent)';
  if (status === 'error') return 'var(--err)';
  return 'var(--ink-muted)';
}


export default function OrgDashboard() {
  const { displayName } = useBrand();
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  // M39: previously `!data` meant both "still loading" and "fetch failed —
  // data never arrived" because the only distinguishing variable was `err`
  // which could be set while `data` was also null. Track loading
  // explicitly so we stop pretending a failed dashboard is "still
  // loading" forever.
  const [loading, setLoading] = useState(true);
  // Theme-aware chart colors — see C19 in the readiness review.
  const themeColors = useThemeColors();
  const ACCENT = themeColors.accent;
  const BORDER = themeColors.border;
  const INK_MUTED = themeColors.inkMuted;
  const TOOLTIP_BG = themeColors.bgElev;

  const load = useCallback(() => {
    setLoading(true);
    api('/orgs/dashboard')
      .then(setData)
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);

  return (
    <AppShell crumbs={['Admin', 'Dashboard']}>
      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}
      {loading && !data ? (
        <LoadingBlock text="Loading dashboard…" />
      ) : !data ? (
        <div className="empty">No dashboard data.</div>
      ) : (
        <>
          {/* Hero: navy gradient with inline stats strip. Replaces the
              previous tile row so KPIs live in one visually-anchored
              location rather than competing for attention with the
              page-title block. */}
          <section className="dash-hero">
            <div className="dash-hero-eyebrow">Admin · {displayName}</div>
            <h1>Your <em>organisation</em> at a glance.</h1>
            <p>
              Members, the agents they're using, and what's been happening
              lately. Open the Agent Library to install more, or jump into a
              specific agent to see run-level detail.
            </p>
            <div className="dash-hero-stats">
              <div>
                <div className="dash-hero-stat-value">{data.totals.members}</div>
                <div className="dash-hero-stat-label">Members</div>
              </div>
              <div>
                <div className="dash-hero-stat-value">{data.totals.installed_agents}</div>
                <div className="dash-hero-stat-label">Installed agents</div>
              </div>
              <div>
                <div className="dash-hero-stat-value">{data.totals.runs}</div>
                <div className="dash-hero-stat-label">Total runs</div>
              </div>
              <div>
                <div className="dash-hero-stat-value">{data.totals.runs_this_week}</div>
                <div className="dash-hero-stat-label">Runs this week</div>
              </div>
            </div>
          </section>

          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8, marginBottom: 14 }}>
            <Link to="/library" className="btn">Agent Library</Link>
            <Link to="/admin/members" className="btn">Members</Link>
          </div>

          <div className="charts-grid">
            <ChartCard title="Runs over time" sub="Last 30 days">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data.trend_30d} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke={BORDER} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date" stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }}
                    tickFormatter={(d) => { try { return new Date(d).toLocaleDateString([], { month: 'short', day: 'numeric' }); } catch { return d; } }}
                    minTickGap={30}
                  />
                  <YAxis stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: TOOLTIP_BG, border: `1px solid ${BORDER}`, fontSize: 12 }} />
                  <Line type="monotone" dataKey="count" stroke={ACCENT} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Agent usage" sub="Runs per agent in this org">
              {data.agent_usage.filter((a) => a.runs > 0).length === 0 ? (
                <div className="empty" style={{ padding: 30, fontSize: 12 }}>
                  No runs yet. <Link to="/library" className="link-btn">Install agents →</Link>
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    layout="vertical"
                    data={data.agent_usage.filter((a) => a.runs > 0).slice(0, 8)}
                    margin={{ top: 4, right: 16, left: 16, bottom: 0 }}
                  >
                    <CartesianGrid stroke={BORDER} strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }} allowDecimals={false} />
                    <YAxis type="category" dataKey="name" stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }} width={160} />
                    <Tooltip contentStyle={{ background: TOOLTIP_BG, border: `1px solid ${BORDER}`, fontSize: 12 }} />
                    <Bar dataKey="runs" fill={ACCENT} radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </ChartCard>
          </div>

          <div className="charts-grid charts-grid--2col">
            <ChartCard title="Top users" sub="By run count">
              {data.top_users.length === 0 ? (
                <div className="empty" style={{ padding: 30, fontSize: 12 }}>No user activity yet.</div>
              ) : (
                <table className="table" style={{ background: 'transparent', border: 0 }}>
                  <thead>
                    <tr>
                      <th>Member</th>
                      <th style={{ textAlign: 'right' }}>Runs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.top_users.map((u) => (
                      <tr key={u.user_id}>
                        <td>
                          <div style={{ color: 'var(--ink)' }}>{u.name}</div>
                          <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{u.email}</div>
                        </td>
                        <td className="mono" style={{ textAlign: 'right' }}>{u.runs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </ChartCard>

            <ChartCard title="Integrations" sub="External systems connected to this org">
              {data.integrations.length === 0 ? (
                <div className="empty" style={{ padding: 30, fontSize: 12 }}>
                  No integrations yet. <Link to="/admin/integrations" className="link-btn">Connect one →</Link>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {data.integrations.map((i) => (
                    <div key={i.id} style={{
                      display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                      padding: '8px 12px',
                      background: 'var(--bg-elev)', border: '1px solid var(--border)',
                      borderRadius: 4, fontSize: 12,
                    }}>
                      <div>
                        <div style={{ color: 'var(--ink)' }}>{i.name}</div>
                        <div style={{ fontSize: 11, color: 'var(--ink-muted)' }}>{i.type}</div>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 2 }}>
                        <span className="cap-tag" style={{ color: statusColor(i.status), borderColor: statusColor(i.status) }}>
                          {i.status}
                        </span>
                        {i.last_tested_at && (
                          <span style={{ fontSize: 10, color: 'var(--ink-muted)' }}>
                            tested {new Date(i.last_tested_at).toLocaleDateString()}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ChartCard>
          </div>

          {data.recent_runs.length > 0 && (
            <>
              <div className="section-header" style={{ marginTop: 22 }}>
                <h2>Recent runs <em>— {data.recent_runs.length}</em></h2>
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Agent</th>
                    <th>User</th>
                    <th>Status</th>
                    <th>Coverage</th>
                    <th style={{ textAlign: 'right' }}>When</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_runs.map((r) => (
                    <tr key={r.id}>
                      <td className="mono">#{r.id}</td>
                      {/* Server-resolved names from the /orgs/dashboard payload.
                          Fall back to the raw id for resilience (e.g. agent
                          uninstalled after the run was recorded). */}
                      <td>{r.agent_name || `agent ${r.agent_id}`}</td>
                      <td>{r.user_name || (r.user_id ? `user ${r.user_id}` : '—')}</td>
                      <td>{r.status}</td>
                      <td className="mono">{r.coverage_pct != null ? `${Math.round(r.coverage_pct)}%` : '—'}</td>
                      <td className="mono" style={{ textAlign: 'right' }}>
                        {r.created_at ? new Date(r.created_at).toLocaleString() : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </>
      )}
    </AppShell>
  );
}
