import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { getOrgId } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';
import { useBrand } from '../lib/brand.js';

function Icon({ d }) {
  return (
    <svg className="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
      {d}
    </svg>
  );
}

const ICONS = {
  hub: <Icon d={<><circle cx="12" cy="12" r="9" /><path d="M12 3v18M3 12h18" /></>} />,
  knowledge: <Icon d={<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14z" />} />,
  runs: <Icon d={<><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>} />,
  members: <Icon d={<><circle cx="9" cy="8" r="3" /><path d="M3 20c0-3 3-5 6-5s6 2 6 5M17 11a3 3 0 1 0 0-6M20 20c0-2-1.5-4-4-4.5" /></>} />,
  depts: <Icon d={<path d="M3 21h18M6 21V8l6-4 6 4v13" />} />,
  audit: <Icon d={<><rect x="3" y="4" width="18" height="16" rx="2" /><path d="M7 9h10M7 13h10M7 17h6" /></>} />,
  platform: <Icon d={<><rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="14" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /></>} />,
  integrations: <Icon d={<><path d="M9 7V4a2 2 0 0 1 4 0v3M6 11h12M7 11v7a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2v-7" /></>} />,
  guide: <Icon d={<><path d="M4 4h11a3 3 0 0 1 3 3v14H7a3 3 0 0 1-3-3V4z" /><path d="M4 18a3 3 0 0 1 3-3h11" /></>} />,
  library: <Icon d={<><path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20V3H6.5A2.5 2.5 0 0 0 4 5.5v14z" /><path d="M9 7h7M9 11h7" /></>} />,
  // "Applications" namespace shares the same nine-dot vibe as platform but
  // drawn as a window/app grid so it reads distinctly from the Agent icons.
  apps: <Icon d={<><rect x="3" y="3" width="7" height="7" rx="1" /><rect x="14" y="3" width="7" height="7" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /><rect x="14" y="14" width="7" height="7" rx="1" /></>} />,
  dashboard: <Icon d={<><rect x="3" y="3" width="7" height="10" /><rect x="14" y="3" width="7" height="7" /><rect x="3" y="16" width="7" height="5" /><rect x="14" y="13" width="7" height="8" /></>} />,
  logout: <Icon d={<><path d="M15 16l4-4-4-4M19 12H9M13 21H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7" /></>} />,
  settings: <Icon d={<><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" /></>} />,
};

/** Thin wrapper around NavLink with our class rules. */
function Item({ to, icon, label, end }) {
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
    >
      {icon}
      {label}
    </NavLink>
  );
}

export default function Sidebar() {
  const { user, isOrgAdmin, isSuperAdmin, logout } = useAuth();
  const { brandMark, tagline, displayName, logoUrl } = useBrand();
  const navigate = useNavigate();
  const [logoFailed, setLogoFailed] = useState(false);

  const isMember = !isOrgAdmin && !isSuperAdmin;

  // Super admins who haven't opened a specific org live in "platform view" —
  // the Tools section ("Agent Library" etc.) is scoped to an org, so it's
  // meaningless without one. They get a dedicated Platform → Agents matrix
  // instead for catalog management across tenants.
  const platformOnly = isSuperAdmin && !getOrgId();

  function handleLogout() {
    logout();
    navigate('/login');
  }

  return (
    <aside id="app-sidebar" className="sidebar" aria-label="Primary navigation">
      {/* Brand block is now vertical: rectangular logo card on top, the
          "AGENT HUB" tagline below it. The org's display name is not
          rendered here — logo alone identifies the tenant. Long names
          could be shown on hover via the image's title attribute. */}
      <div className="sidebar-brand">
        {logoUrl && !logoFailed ? (
          <div className="sidebar-brand-logo">
            <img
              src={logoUrl}
              alt={displayName}
              title={displayName}
              onError={() => setLogoFailed(true)}
            />
          </div>
        ) : (
          <div className="sidebar-brand-mark" title={displayName} />
        )}
        <div
          style={{
            fontSize: 11,
            letterSpacing: '0.16em',
            color: 'var(--ink-muted)',
            textTransform: 'uppercase',
            fontWeight: 600,
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            paddingLeft: 2,
          }}
        >
          {tagline}
        </div>
      </div>

      {/* ── Role-specific nav ───────────────────────────────────────── */}

      {isSuperAdmin && (
        <>
          <div className="nav-label">Platform</div>
          <Item to="/platform/dashboard" icon={ICONS.dashboard} label="Dashboard" />
          <Item to="/platform/orgs" icon={ICONS.platform} label="Organizations" />
          <Item to="/platform/agents" icon={ICONS.library} label="Agents" />
        </>
      )}

      {/* Admin section — visible whenever there's an active org to administer:
          either a regular ORG_ADMIN (never super admin) or a super admin who
          has explicitly opened an org via Platform → Organizations → Open →.
          Without an active org, super admins only see Platform nav. */}
      {((isOrgAdmin && !isSuperAdmin) || (isSuperAdmin && !platformOnly)) && (
        <>
          <div className="nav-label">Admin</div>
          <Item to="/admin/dashboard" icon={ICONS.dashboard} label="Dashboard" />
          <Item to="/admin/members" icon={ICONS.members} label="Members" />
          <Item to="/admin/departments" icon={ICONS.depts} label="Departments" />
          <Item to="/admin/integrations" icon={ICONS.integrations} label="Integrations" />
          <Item to="/admin/audit" icon={ICONS.audit} label="Audit Log" />
        </>
      )}

      {/* Shared workspace links. Knowledge Base and My Runs are intentionally
          NOT in the sidebar until their routes are real (L4 in the readiness
          review). The routes still exist in App.jsx so any linked URL renders
          a clean "coming soon", but we stop advertising unimplemented pages. */}
      {!platformOnly && (
        <>
          <div className="nav-label">{isMember ? 'Workspace' : 'Tools'}</div>
          {/* Order: My Agents → My Applications → Agent Library → Application
              Library. Both "My …" entries use `end` so they don't co-highlight
              with the library routes that share the URL prefix. */}
          {isMember && <Item to="/" end icon={ICONS.hub} label="My Agents" />}
          {/* Applications namespace runs in parallel with Agents — same
              install / pick / department semantics under the hood, just
              surfaced separately so apps with their own multi-page flow
              (e.g. Prism / CACM) don't get lost in the agent grid. */}
          {isMember && <Item to="/applications" end icon={ICONS.apps} label="My Applications" />}
          <Item to="/library" icon={ICONS.library} label="Agent Library" />
          <Item to="/applications/library" icon={ICONS.library} label="Application Library" />
          <Item to="/guide" icon={ICONS.guide} label="User Guide" />
        </>
      )}
      {platformOnly && <div className="nav-label">Account</div>}
      <Item to="/settings" icon={ICONS.settings} label="Settings" />

      <div style={{ flex: 1 }} />

      <div style={{
        padding: '14px 20px',
        borderTop: '1px solid var(--border)',
        fontSize: 12,
        color: 'var(--ink-dim)',
        display: 'flex',
        gap: 10,
        alignItems: 'center',
        justifyContent: 'space-between',
      }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ color: 'var(--ink)', overflow: 'hidden', textOverflow: 'ellipsis' }}>{user?.name}</div>
          <div style={{ color: 'var(--ink-muted)', fontSize: 11, overflow: 'hidden', textOverflow: 'ellipsis' }}>
            {user?.email}
          </div>
        </div>
        <button
          type="button"
          className="sidebar-logout"
          onClick={handleLogout}
          title="Log out"
        >
          {ICONS.logout}
        </button>
      </div>
    </aside>
  );
}
