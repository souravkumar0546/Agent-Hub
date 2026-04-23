import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
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
import { api, setOrgId } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';
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


export default function PlatformDashboard() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [data, setData] = useState(null);
  const [err, setErr] = useState('');
  // Theme-aware chart colors — re-reads CSS tokens when the theme flips so
  // axes/tooltip/fills no longer stay neon-on-white in light mode (C19).
  const themeColors = useThemeColors();
  const ACCENT = themeColors.accent;
  const BORDER = themeColors.border;
  const INK_MUTED = themeColors.inkMuted;
  const TOOLTIP_BG = themeColors.bgElev;

  const load = useCallback(() => {
    api('/platform/dashboard')
      .then(setData)
      .catch((e) => setErr(e.message));
  }, []);
  useEffect(load, [load]);

  async function openOrg(orgId) {
    setOrgId(orgId);
    sessionStorage.setItem('sah.asOrg', String(orgId));
    if (refresh) await refresh();
    navigate('/');
  }

  return (
    <AppShell crumbs={['Platform', 'Dashboard']}>
      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}
      {!data ? (
        <div className="empty">Loading platform metrics…</div>
      ) : (
        <>
          {/* Navy-gradient dashboard hero with inline stats strip —
              mirrors the Uniqus Accelerators portfolio header. */}
          <section className="dash-hero">
            <div className="dash-hero-eyebrow">Platform · Super Admin</div>
            <h1>Every <em>tenant</em>, every agent run, one view.</h1>
            <p>
              Monitor the agents installed across every organisation, who's
              running them, and where activity is trending. Drill into any
              tenant from the Organizations page.
            </p>
            <div className="dash-hero-stats">
              <div>
                <div className="dash-hero-stat-value">{data.totals.orgs}</div>
                <div className="dash-hero-stat-label">Organizations</div>
              </div>
              <div>
                <div className="dash-hero-stat-value">{data.totals.users}</div>
                <div className="dash-hero-stat-label">Users</div>
              </div>
              <div>
                <div className="dash-hero-stat-value">{data.totals.memberships}</div>
                <div className="dash-hero-stat-label">Memberships</div>
              </div>
              <div>
                <div className="dash-hero-stat-value">{data.totals.agents_installed}</div>
                <div className="dash-hero-stat-label">Agents Installed</div>
              </div>
              <div>
                <div className="dash-hero-stat-value">{data.totals.runs}</div>
                <div className="dash-hero-stat-label">Lifetime Runs</div>
              </div>
            </div>
          </section>

          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 14 }}>
            <button className="btn btn-primary" onClick={() => navigate('/platform/orgs')}>
              Manage organizations →
            </button>
          </div>

          <div className="charts-grid">
            <ChartCard title="Runs across the platform" sub="Last 30 days, every org">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data.trend_30d} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke={BORDER} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date" stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }}
                    tickFormatter={(d) => {
                      try { return new Date(d).toLocaleDateString([], { month: 'short', day: 'numeric' }); }
                      catch { return d; }
                    }}
                    minTickGap={30}
                  />
                  <YAxis stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: TOOLTIP_BG, border: `1px solid ${BORDER}`, fontSize: 12 }} />
                  <Line type="monotone" dataKey="count" stroke={ACCENT} strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="New users" sub="Signups in the last 30 days">
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={data.signups_30d} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
                  <CartesianGrid stroke={BORDER} strokeDasharray="3 3" />
                  <XAxis dataKey="date" stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }}
                    tickFormatter={(d) => { try { return new Date(d).toLocaleDateString([], { month: 'short', day: 'numeric' }); } catch { return d; } }}
                    minTickGap={30} />
                  <YAxis stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: TOOLTIP_BG, border: `1px solid ${BORDER}`, fontSize: 12 }} />
                  <Line type="monotone" dataKey="count" stroke={ACCENT} strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard title="Top agents platform-wide" sub="Ranked by total runs">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart layout="vertical" data={data.top_agents.slice(0, 8)} margin={{ top: 4, right: 16, left: 16, bottom: 0 }}>
                  <CartesianGrid stroke={BORDER} strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }} allowDecimals={false} />
                  <YAxis type="category" dataKey="name" stroke={BORDER} tick={{ fill: INK_MUTED, fontSize: 10 }} width={160} />
                  <Tooltip contentStyle={{ background: TOOLTIP_BG, border: `1px solid ${BORDER}`, fontSize: 12 }} />
                  <Bar dataKey="runs" fill={ACCENT} radius={[0, 3, 3, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>
          </div>

          <div className="section-header" style={{ marginTop: 22 }}>
            <h2>Organizations <em>— {data.orgs.length}</em></h2>
          </div>
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
              {data.orgs.map((o) => (
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
                    <button className="link-btn" onClick={() => openOrg(o.id)}>Open →</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {data.recent_runs.length > 0 && (
            <>
              <div className="section-header" style={{ marginTop: 22 }}>
                <h2>Recent runs <em>— platform-wide</em></h2>
              </div>
              <table className="table">
                <thead>
                  <tr>
                    <th>Run</th>
                    <th>Org</th>
                    <th>Agent</th>
                    <th>Status</th>
                    <th>Coverage</th>
                    <th style={{ textAlign: 'right' }}>When</th>
                  </tr>
                </thead>
                <tbody>
                  {data.recent_runs.map((r) => (
                    <tr key={r.id}>
                      <td className="mono">#{r.id}</td>
                      {/* Server-resolved names land in `org_name`/`agent_name`;
                          fall back to the raw id only if something racy
                          happened (e.g. org deleted between query + render). */}
                      <td>{r.org_name || `org ${r.org_id}`}</td>
                      <td>{r.agent_name || `agent ${r.agent_id}`}</td>
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
