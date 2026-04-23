import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import AppShell from '../components/AppShell.jsx';
import AgentIcon from '../components/AgentIcon.jsx';
import { useToast } from '../components/Dialog.jsx';
import { api, downloadFile } from '../lib/api.js';
import { useThemeColors } from '../lib/useThemeColors.js';

const AGENT_TYPE = 'rca_investigation';

const PHASE_LABELS = {
  intake: 'Intake',
  gap_analysis: 'Gap analysis',
  targeted_qa: 'Targeted Q&A',
  drafting: 'Drafting',
  review: 'Review',
  complete: 'Complete',
};

/** Build the phase → colour map from the active theme palette.
 *  Each phase maps to a semantic token so light mode picks up its darker
 *  variants automatically instead of rendering the dark-mode neon green on
 *  white (M44). Call from inside a component (where `useThemeColors` has
 *  been resolved) rather than at module scope. */
function buildPhaseColors(colors) {
  return {
    intake: colors.bio,
    gap_analysis: colors.pink,
    targeted_qa: colors.warn,
    drafting: colors.accent,
    review: colors.accentSoft,
    complete: colors.inkDim,
  };
}

function formatDuration(ms) {
  if (!ms) return '—';
  if (ms < 1000) return `${ms} ms`;
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60);
  const rem = s - m * 60;
  return `${m}m ${rem}s`;
}

function formatDate(iso) {
  if (!iso) return '—';
  try {
    const d = new Date(iso);
    return d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
  } catch { return iso; }
}

function PhasePill({ phase, phaseColors }) {
  return (
    <span className="pill" style={{
      // Subtle theme-aware tint: rgba of the current accent at very low alpha
      // so the pill reads on both light and dark canvases (H45 replaced the
      // hardcoded white-with-3%-alpha that looked fine only on dark).
      background: 'rgba(var(--accent-rgb), 0.05)',
      borderColor: 'var(--border)',
      color: phaseColors[phase] || 'var(--ink-dim)',
    }}>{PHASE_LABELS[phase] || phase}</span>
  );
}

function Tile({ label, value, sub, delta, accent }) {
  const deltaColor = delta == null
    ? 'var(--ink-muted)'
    : delta >= 0 ? 'var(--accent)' : 'var(--err)';
  const deltaSign = delta == null ? '' : (delta > 0 ? '+' : '');
  return (
    <div className="tile">
      <div className="tile-label">{label}</div>
      <div className="tile-value" style={{ color: accent ? 'var(--accent)' : 'var(--ink)' }}>
        {value}
      </div>
      <div className="tile-meta">
        {sub && <span>{sub}</span>}
        {delta != null && (
          <span style={{ color: deltaColor }}>{deltaSign}{delta}% vs last</span>
        )}
      </div>
    </div>
  );
}

/* ── Page ──────────────────────────────────────────────────────────── */

export default function InvestigationDashboard() {
  const navigate = useNavigate();
  const [agent, setAgent] = useState(null);
  const [stats, setStats] = useState(null);
  const [runs, setRuns] = useState([]);
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);
  const toast = useToast();
  const themeColors = useThemeColors();
  const phaseColors = useMemo(() => buildPhaseColors(themeColors), [themeColors]);

  // Filters
  const [phaseFilter, setPhaseFilter] = useState('');     // phase slug or ''
  const [coverageFilter, setCoverageFilter] = useState(0); // min coverage
  const [range, setRange] = useState('all');              // 'all' | '7d' | '30d'

  const loadAll = useCallback(async () => {
    setLoading(true);
    try {
      // Agent IDs are per-org (Syngene's Investigation is id 11, Uniqus's is
      // 27, etc). Resolve the id by type within the caller's org context
      // before hitting the stats/runs endpoints.
      const agents = await api('/agents?scope=installed');
      const match = agents.find((a) => a.type === AGENT_TYPE);
      if (!match) {
        throw new Error('Investigation agent is not installed in this organisation. Ask an admin to install it from the Agent Library.');
      }
      const [s, r] = await Promise.all([
        api(`/agents/${match.id}/stats`),
        api(`/agents/${match.id}/runs?limit=100`),
      ]);
      setAgent(match);
      setStats(s);
      setRuns(r);
      setErr('');
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Derive table rows — roots of each chain only, with chain length.
  const investigations = useMemo(() => {
    // Group runs by their root (root = earliest ancestor with parent_run_id=null).
    const byId = new Map(runs.map((r) => [r.id, r]));
    function rootOf(r) {
      let cur = r;
      while (cur.parent_run_id && byId.has(cur.parent_run_id)) cur = byId.get(cur.parent_run_id);
      return cur;
    }
    const grouped = new Map();
    for (const r of runs) {
      const root = rootOf(r);
      const arr = grouped.get(root.id) || [];
      arr.push(r);
      grouped.set(root.id, arr);
    }
    const list = [];
    for (const [rootId, members] of grouped) {
      const root = byId.get(rootId);
      if (!root) continue;
      const latest = members.reduce((a, b) => (a.id > b.id ? a : b));
      // `investigation_no` is the per-org sequence (1 = first investigation
      // in this org). Fall back to the global id only if the backend hasn't
      // populated it (older payloads).
      const invNo = root.investigation_no ?? root.id;
      list.push({
        root_id: root.id,
        investigation_no: invNo,
        latest_id: latest.id,
        preview: root.preview || latest.preview || `Investigation #${invNo}`,
        created_at: root.created_at,
        coverage_pct: latest.coverage_pct ?? 0,
        phase: latest.phase || 'intake',
        turns: members.length,
        duration_ms: members.reduce((sum, m) => sum + (m.duration_ms || 0), 0),
      });
    }
    list.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
    return list;
  }, [runs]);

  const filtered = useMemo(() => {
    const now = Date.now();
    const cutoff = range === '7d' ? now - 7 * 86400000 : range === '30d' ? now - 30 * 86400000 : null;
    return investigations.filter((inv) => {
      if (phaseFilter && inv.phase !== phaseFilter) return false;
      if (inv.coverage_pct < coverageFilter) return false;
      if (cutoff && new Date(inv.created_at).getTime() < cutoff) return false;
      return true;
    });
  }, [investigations, phaseFilter, coverageFilter, range]);

  const totals = stats?.totals || {};
  const averages = stats?.averages || {};

  async function downloadRun(runId) {
    try {
      await downloadFile(`/runs/${runId}/export.docx`, `Investigation_${runId}.docx`);
    } catch (e) {
      toast(`Export failed: ${e.message}`, { variant: 'error' });
    }
  }

  return (
    <AppShell crumbs={['Agent Hub', agent?.name || 'Investigation', 'Dashboard']}>
      {/* Header: identical shape to other agent pages — title block on the
          left, "← Agent Hub" on the right. The primary CTA sits below in its
          own row so it has room to breathe. */}
      <div className="inv-dash-header">
        <div className="agent-icon" style={{ width: 48, height: 48 }}>
          <AgentIcon name={agent?.icon || 'search'} size={24} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Title uses the short brand-style `display_name` ("Devio") with
              the long name shown small underneath — matches the pattern on
              Agent Library / My Agents cards. Falls back to hardcoded
              strings only while the agent is still loading. */}
          <h1 className="page-title" style={{ marginBottom: 4 }}>
            {agent?.display_name || agent?.name || 'Devio'}
          </h1>
          {agent?.display_name && agent.display_name !== agent.name && (
            <div
              style={{
                fontSize: 12,
                fontWeight: 500,
                color: 'var(--ink-muted)',
                letterSpacing: '0.02em',
                marginTop: -2,
                marginBottom: 6,
              }}
            >
              {agent.name}
            </div>
          )}
          <div className="page-subtitle" style={{ marginBottom: 10 }}>
            {agent?.tagline || 'Deviation intake, root-cause analysis, and investigation report drafting.'}
          </div>
          <div className="agent-meta">
            {(agent?.departments || []).map((d) => (
              <span key={d.id} className="cap-tag">{d.name}</span>
            ))}
          </div>
        </div>
        <Link to="/" className="btn">← Agent Hub</Link>
      </div>

      <div className="inv-dash-cta">
        <Link to="/agents/rca_investigation/chat" className="btn btn-primary">+ New Investigation</Link>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 16 }}>{err}</div>}

      {loading && !stats ? (
        <div className="empty">Loading dashboard…</div>
      ) : !stats ? null : (
        <>
          {/* Tiles */}
          <div className="tiles">
            <Tile
              label="Total investigations"
              value={totals.investigations}
              sub={`${totals.this_month} this month`}
            />
            <Tile
              label="This week"
              value={totals.this_week}
              delta={totals.week_delta_pct}
            />
            <Tile
              label="Avg coverage"
              value={`${averages.coverage_pct ?? 0}%`}
              sub="per investigation"
              accent
            />
            <Tile
              label="Completion rate"
              value={`${stats.completion_rate}%`}
              sub="Review + ≥90% coverage"
            />
            <Tile
              label="Avg duration"
              value={formatDuration(averages.duration_ms)}
              sub="per AI turn"
            />
          </div>

          {/* Charts were removed here by user request — the tile row above is
              the whole top-of-page summary now. The /agents/{id}/stats endpoint
              is still called for the tile values; its trend_30d / coverage
              histogram / phase distribution / weekly success / top_sops fields
              are simply unused on this page. */}

          {/* Filters + table */}
          <div className="section-header" style={{ marginTop: 24 }}>
            <h2>Recent investigations <em>— {filtered.length}</em></h2>
          </div>

          <div className="filter-row">
            <button className={`filter-chip${range === 'all' ? ' active' : ''}`} onClick={() => setRange('all')}>All time</button>
            <button className={`filter-chip${range === '30d' ? ' active' : ''}`} onClick={() => setRange('30d')}>Last 30 days</button>
            <button className={`filter-chip${range === '7d' ? ' active' : ''}`} onClick={() => setRange('7d')}>Last 7 days</button>
            <span style={{ borderLeft: '1px solid var(--border)', margin: '0 6px' }} />
            <button className={`filter-chip${phaseFilter === '' ? ' active' : ''}`} onClick={() => setPhaseFilter('')}>All phases</button>
            {['intake', 'gap_analysis', 'targeted_qa', 'drafting', 'review'].map((p) => (
              <button
                key={p}
                className={`filter-chip${phaseFilter === p ? ' active' : ''}`}
                onClick={() => setPhaseFilter(p)}
              >{PHASE_LABELS[p]}</button>
            ))}
            <span style={{ borderLeft: '1px solid var(--border)', margin: '0 6px' }} />
            <button className={`filter-chip${coverageFilter === 0 ? ' active' : ''}`} onClick={() => setCoverageFilter(0)}>Any coverage</button>
            <button className={`filter-chip${coverageFilter === 50 ? ' active' : ''}`} onClick={() => setCoverageFilter(50)}>≥ 50%</button>
            <button className={`filter-chip${coverageFilter === 90 ? ' active' : ''}`} onClick={() => setCoverageFilter(90)}>≥ 90%</button>
          </div>

          {filtered.length === 0 ? (
            <div className="empty">No investigations match that filter.</div>
          ) : (
            <table className="table inv-dash-table">
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Started</th>
                  <th style={{ width: '40%' }}>Deviation</th>
                  <th>Coverage</th>
                  <th>Phase</th>
                  <th>Turns</th>
                  <th>Duration</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {filtered.slice(0, 10).map((inv) => (
                  <tr
                    key={inv.root_id}
                    className="inv-dash-row"
                    onClick={() => navigate(`/agents/rca_investigation/chat/${inv.latest_id}`)}
                  >
                    <td className="mono">#{inv.investigation_no}</td>
                    <td>{formatDate(inv.created_at)}</td>
                    <td className="ellipsis">{inv.preview}</td>
                    <td>
                      <div className="coverage-bar" title={`${inv.coverage_pct}%`}>
                        <div className="coverage-bar-fill" style={{ width: `${Math.min(100, inv.coverage_pct)}%` }} />
                        <span>{Number(inv.coverage_pct).toFixed(0)}%</span>
                      </div>
                    </td>
                    <td><PhasePill phase={inv.phase} phaseColors={phaseColors} /></td>
                    <td className="mono">{inv.turns}</td>
                    <td className="mono">{formatDuration(inv.duration_ms)}</td>
                    <td style={{ textAlign: 'right' }} onClick={(e) => e.stopPropagation()}>
                      <button className="link-btn" onClick={() => navigate(`/agents/rca_investigation/chat/${inv.latest_id}`)}>Open</button>
                      {' · '}
                      <button className="link-btn" onClick={() => downloadRun(inv.latest_id)}>DOCX</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </AppShell>
  );
}
