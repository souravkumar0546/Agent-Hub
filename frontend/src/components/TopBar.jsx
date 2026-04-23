import { useState } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import { setOrgId } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';
import { useBrand, useDocumentTitle } from '../lib/brand.js';


/** Small rounded thumbnail — logo if set, monogram fallback. */
function BrandThumb({ url, name, size = 30 }) {
  const [failed, setFailed] = useState(false);
  const letter = (name || '?').trim().charAt(0).toUpperCase();
  const base = {
    width: size, height: size, borderRadius: Math.round(size / 4),
    border: '1px solid var(--border)',
    flexShrink: 0,
    overflow: 'hidden',
    display: 'grid', placeItems: 'center',
    background: 'var(--bg)',
  };
  if (url && !failed) {
    return (
      <div style={base} title={name}>
        <img
          src={url}
          alt={name || 'Org logo'}
          onError={() => setFailed(true)}
          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
        />
      </div>
    );
  }
  return (
    <div style={{
      ...base,
      background: 'rgba(var(--accent-rgb), 0.1)',
      color: 'var(--accent)',
      fontFamily: 'var(--serif)', fontStyle: 'italic',
      fontSize: Math.round(size * 0.5), fontWeight: 500,
    }} title={name}>
      {letter}
    </div>
  );
}


/** Convert a backend role token ("ORG_ADMIN") into short user-facing copy. */
function roleLabel(user) {
  if (!user) return '';
  if (user.is_super_admin) return 'Super admin';
  const r = (user.current_org_role || '').toUpperCase();
  if (r === 'ORG_ADMIN') return 'Admin';
  if (r === 'MEMBER') return 'Member';
  return r ? r.replace(/_/g, ' ').toLowerCase() : '';
}


/** User chip in the top-right: round initial + name + role below.
 *
 *  Replaces the previous org-name-chip + tiny-round-avatar pair. Clicking
 *  the whole chip opens Settings — same as before. On very narrow
 *  viewports the name/role text collapses via CSS so just the circle
 *  remains.
 */
function UserChip({ user }) {
  const displayName = user?.name || user?.email || 'Signed in';
  const letter = displayName.trim().charAt(0).toUpperCase() || '?';
  const role = roleLabel(user);
  return (
    <NavLink
      to="/settings"
      className="topbar-userchip"
      title={`${displayName}${role ? ' · ' + role : ''} — open Settings`}
    >
      <span className="topbar-userchip-avatar" aria-hidden="true">{letter}</span>
      <span className="topbar-userchip-meta">
        <span className="topbar-userchip-name">{displayName}</span>
        {role && <span className="topbar-userchip-role">{role}</span>}
      </span>
    </NavLink>
  );
}


export default function TopBar({ crumbs = [], onToggleNav, navOpen = false }) {
  const { user, refresh, switchOrg } = useAuth();
  const { brandLine, displayName, logoUrl } = useBrand();
  const navigate = useNavigate();

  useDocumentTitle(crumbs.length ? crumbs[crumbs.length - 1] : '');

  const viewingAsOrg = typeof sessionStorage !== 'undefined' && !!sessionStorage.getItem('sah.asOrg');

  async function backToPlatform() {
    sessionStorage.removeItem('sah.asOrg');
    setOrgId(null);
    if (refresh) await refresh();
    navigate('/platform/orgs');
  }

  return (
    <div className="topbar">
      {/* Mobile-only hamburger toggle for the slide-in sidebar. Hidden on
          desktop via CSS media query; on narrow viewports it sits left of
          the crumbs. The aria-expanded/controls pair keeps the drawer state
          legible to screen readers. */}
      {onToggleNav && (
        <button
          type="button"
          className="topbar-hamburger"
          aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
          aria-expanded={navOpen}
          aria-controls="app-sidebar"
          onClick={onToggleNav}
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
            <path d="M4 7h16M4 12h16M4 17h16" />
          </svg>
        </button>
      )}
      <div className="topbar-crumbs">
        <span>{brandLine}</span>
        {crumbs.map((c, i) => (
          <span key={i} className={i === crumbs.length - 1 ? 'current' : ''}>
            <span style={{ margin: '0 6px', color: 'var(--ink-muted)' }}>/</span>
            {c}
          </span>
        ))}
      </div>

      <div className="topbar-spacer" />

      {user?.is_super_admin && viewingAsOrg && (
        <button
          className="topbar-ghost-btn"
          onClick={backToPlatform}
          title="Leave org view and return to the Platform dashboard"
        >
          ← Platform
        </button>
      )}

      {/* Multi-org users keep the tenant switcher — it's the only way to
          change active org from the shell. Single-org users see just their
          user chip on the right; the org identity already lives in the
          sidebar logo + the dashboard hero, so a separate name chip here
          was redundant. */}
      {user?.orgs?.length > 1 && (
        <div className="topbar-orgpicker">
          <BrandThumb url={logoUrl} name={displayName} size={24} />
          <select
            value={user.current_org_id || ''}
            onChange={(e) => switchOrg(Number(e.target.value))}
            aria-label="Switch organisation"
          >
            {user.orgs.map((o) => (
              <option key={o.id} value={o.id}>{o.name}</option>
            ))}
          </select>
        </div>
      )}

      <UserChip user={user} />
    </div>
  );
}
