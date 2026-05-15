import { useEffect, useMemo, useState } from 'react';
import { Link, Navigate } from 'react-router-dom';
import AgentIcon from '../components/AgentIcon.jsx';
import AppShell from '../components/AppShell.jsx';
import { api, getOrgId } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';


// The hub renders two parallel namespaces — Agents (default) and
// Applications. They differ only in copy, breadcrumbs, the kind filter
// applied to the listing call, and the library link. Everything else
// (scope handling, dept chips, redirect behaviour) is identical, so we
// drive both off a single `kind` prop.
export default function AgentHubPage({ kind = 'agent' }) {
  const { user, isSuperAdmin, isOrgAdmin } = useAuth();

  const isApp = kind === 'application';
  const libraryHref = isApp ? '/applications/library' : '/library';
  const noun = isApp ? 'application' : 'agent';
  const Noun = isApp ? 'Application' : 'Agent';
  const nouns = `${noun}s`;
  const Nouns = `${Noun}s`;
  const crumb = isApp ? 'Application Hub' : 'Agent Hub';

  // Super-admins land on the platform dashboard unless they've explicitly
  // opened a specific org via the platform page (session flag).
  const viewingAsOrg = typeof sessionStorage !== 'undefined' && sessionStorage.getItem('sah.asOrg');
  if (isSuperAdmin && !viewingAsOrg) {
    return <Navigate to="/platform/dashboard" replace />;
  }
  // Org admins land on the org dashboard instead of the hub.
  if (isOrgAdmin && !isSuperAdmin) {
    return <Navigate to="/admin/dashboard" replace />;
  }

  // Members: their Hub is their picked agents. Scope = 'picked' for members,
  // scope = 'installed' for admins (when super-admins open an org from the
  // platform page, they see the full installed catalog as admins would).
  const scope = isOrgAdmin || isSuperAdmin ? 'installed' : 'picked';

  const [agents, setAgents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [activeDept, setActiveDept] = useState('');
  // null = loading / unknown. Members see their own count; admins see org-wide
  // once they're viewing a specific org (admins are redirected off this page
  // in most cases anyway). Refreshed on mount only — refetching on every nav
  // is overkill for a counter that barely moves.
  const [runsToday, setRunsToday] = useState(null);

  useEffect(() => {
    setLoading(true);
    api(`/agents?scope=${scope}&kind=${kind}`)
      .then((list) => { setAgents(list); setErr(''); })
      .catch((e) => setErr(e.message))
      .finally(() => setLoading(false));
  }, [scope, kind]);

  useEffect(() => {
    // Personal dashboard gives us today's run count scoped to this user + org.
    // Fail silently — the stat card degrades to '—' if the call errors.
    api('/me/dashboard')
      .then((d) => setRunsToday(d?.totals?.runs_today ?? 0))
      .catch(() => setRunsToday(null));
  }, []);

  const deptOptions = useMemo(() => {
    // Collect unique departments across all visible agents. We require a slug
    // here — the backend now returns one for every dept (see IdName). If an
    // agent's dept arrives without one (stale cache, mocked fixture), skip it
    // rather than silently falling through to `.id` and breaking the filter.
    const seen = new Map();
    for (const a of agents) {
      for (const d of a.departments || []) {
        if (!d.slug) continue;
        if (!seen.has(d.slug)) seen.set(d.slug, d.name);
      }
    }
    return Array.from(seen.entries()).map(([slug, name]) => ({ slug, name }));
  }, [agents]);

  const filtered = useMemo(() => {
    if (!activeDept) return agents;
    return agents.filter((a) => (a.departments || []).some((d) => d.slug === activeDept));
  }, [agents, activeDept]);

  const deptCount = user?.departments?.length || 0;

  return (
    <AppShell crumbs={[crumb]}>
      <section className="hero">
        <div>
          <h1>
            Your <em>{nouns}</em>, ready to work.
          </h1>
          <p>
            {scope === 'picked'
              ? `${Nouns} in your personal workspace. Add more from the ${Noun} Library when you need them.`
              : `Every ${noun} installed in this organisation. Members pick the ones they need into their own workspace.`}
          </p>
        </div>
        <div className="stats">
          <div className="stat">
            <div className="stat-label">{scope === 'picked' ? 'In your workspace' : 'Installed'}</div>
            <div className="stat-value">{agents.length}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Your departments</div>
            <div className="stat-value">{deptCount}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Runs today</div>
            <div className="stat-value">{runsToday == null ? '—' : runsToday}</div>
          </div>
        </div>
      </section>

      {err && <div style={{ color: 'var(--err)', marginBottom: 16 }}>Error: {err}</div>}

      <div className="section-header">
        <h2>
          {scope === 'picked' ? `My ${nouns}` : `Installed ${nouns}`} <em>— {filtered.length}{activeDept ? ` / ${agents.length}` : ''}</em>
        </h2>
        <Link to={libraryHref} className="btn btn-primary">
          {scope === 'picked' ? '+ Add from library' : 'Manage library'}
        </Link>
      </div>

      {deptOptions.length > 0 && (
        <div className="filter-row">
          <button className={`filter-chip${activeDept === '' ? ' active' : ''}`} onClick={() => setActiveDept('')}>All</button>
          {deptOptions.map((d) => (
            <button
              key={d.slug}
              className={`filter-chip${activeDept === d.slug ? ' active' : ''}`}
              onClick={() => setActiveDept(d.slug)}
            >
              {d.name}
            </button>
          ))}
        </div>
      )}

      {loading ? (
        <div className="empty">Loading {nouns}…</div>
      ) : filtered.length === 0 ? (
        <div className="empty" style={{ textAlign: 'center' }}>
          {scope === 'picked' ? (
            <>
              <div style={{ fontFamily: 'var(--sans)', fontWeight: 800, fontSize: 22, letterSpacing: '-0.02em', marginBottom: 8, color: 'var(--ink)' }}>
                Your workspace is empty
              </div>
              <div style={{ fontSize: 13, marginBottom: 14 }}>
                Pick {nouns} from the library to add them here — they'll appear on this page and their activity will show up on your dashboard.
              </div>
              <Link to={libraryHref} className="btn btn-primary">Open the {Noun} Library →</Link>
            </>
          ) : (
            <>
              <div style={{ fontFamily: 'var(--sans)', fontWeight: 800, fontSize: 22, letterSpacing: '-0.02em', marginBottom: 8, color: 'var(--ink)' }}>
                No {nouns} installed
              </div>
              <div style={{ fontSize: 13, marginBottom: 14 }}>
                Install {nouns} from the catalog to make them available to your members.
              </div>
              <Link to={libraryHref} className="btn btn-primary">Open the {Noun} Library →</Link>
            </>
          )}
        </div>
      ) : (
        <div className="agent-grid">
          {filtered.map((a) => (
            <Link key={a.id} to={`/agents/${a.type}`} state={{ agent: a }} className="agent-card">
              <div className="agent-icon">
                <AgentIcon name={a.icon || 'chart'} />
              </div>
              {/* Brand name primary, long name as subtitle when distinct. */}
              <div className="agent-name">{a.display_name || a.name}</div>
              {a.display_name && a.display_name !== a.name && (
                <div className="agent-subname" title={a.name}>{a.name}</div>
              )}
              <div className="agent-tagline">{a.tagline}</div>
              <div className="agent-meta">
                <span className="cap-tag cap-tag--accent">{a.category}</span>
                {a.departments.length === 0 ? (
                  <span className="cap-tag">Org-wide</span>
                ) : (
                  a.departments.slice(0, 3).map((d) => <span key={d.id} className="cap-tag">{d.name}</span>)
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </AppShell>
  );
}
