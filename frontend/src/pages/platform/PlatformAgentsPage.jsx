import { useCallback, useEffect, useMemo, useState } from 'react';
import AgentIcon from '../../components/AgentIcon.jsx';
import AppShell from '../../components/AppShell.jsx';
import { useConfirm, useToast } from '../../components/Dialog.jsx';
import { api } from '../../lib/api.js';


/** Small org-logo thumb reused in dropdown + section headers. */
function OrgThumb({ org, size = 22 }) {
  const [failed, setFailed] = useState(false);
  const letter = (org?.name || '?').trim().charAt(0).toUpperCase();
  const base = {
    width: size, height: size, borderRadius: Math.round(size / 4),
    border: '1px solid var(--border)',
    flexShrink: 0,
    overflow: 'hidden',
    display: 'grid', placeItems: 'center',
    background: 'var(--bg)',
  };
  if (org?.logo_url && !failed) {
    return (
      <div style={base} title={org.name}>
        <img
          src={org.logo_url}
          alt={org.name}
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
      fontSize: Math.round(size * 0.55), fontWeight: 500,
    }} title={org?.name}>
      {letter}
    </div>
  );
}


/**
 * Platform-level agent management.
 *
 * UX: pick an org from the dropdown → see two lists — "Granted" (revocable)
 * and "Not granted" (grant-able). Super admin only grants or revokes; they
 * don't touch install state or department scope (that's the org admin's
 * call, exposed here only as read-only info).
 */
export default function PlatformAgentsPage() {
  const [orgs, setOrgs] = useState([]);
  const [catalog, setCatalog] = useState([]);
  const [installations, setInstallations] = useState([]);
  const [departmentsByOrg, setDepartmentsByOrg] = useState({});
  const [err, setErr] = useState('');
  const [loading, setLoading] = useState(true);
  const [orgId, setOrgId] = useState(null);
  const [busyType, setBusyType] = useState(null);
  const confirm = useConfirm();
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api('/platform/agents');
      setOrgs(data.orgs);
      setCatalog(data.catalog);
      setInstallations(data.installations);
      setDepartmentsByOrg(data.departments_by_org || {});
      // Default-select the first org the first time we load.
      setOrgId((prev) => prev ?? (data.orgs[0]?.id ?? null));
      setErr('');
    } catch (e) {
      setErr(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const org = orgs.find((o) => o.id === orgId) || null;

  // For the chosen org, split the catalog into granted vs not-granted.
  const { granted, notGranted } = useMemo(() => {
    if (!org) return { granted: [], notGranted: [] };
    const instByType = new Map(
      installations
        .filter((i) => i.org_id === org.id)
        .map((i) => [i.agent_type, i]),
    );
    const grantedList = [];
    const notGrantedList = [];
    for (const entry of catalog) {
      const inst = instByType.get(entry.type);
      if (inst && inst.granted_by_platform) {
        grantedList.push({ entry, installation: inst });
      } else {
        // Not implemented entries still go into "not granted" but with a
        // disabled grant button (rendered below).
        notGrantedList.push({ entry, installation: inst || null });
      }
    }
    return { granted: grantedList, notGranted: notGrantedList };
  }, [org, catalog, installations]);

  // Build id → name map for the currently-selected org's departments so we
  // can render the org admin's chosen scope inline.
  const deptNameById = useMemo(() => {
    if (!org) return {};
    const list = departmentsByOrg[String(org.id)] || departmentsByOrg[org.id] || [];
    return Object.fromEntries(list.map((d) => [d.id, d.name]));
  }, [org, departmentsByOrg]);

  function scopeLabel(installation) {
    if (!installation) return null;
    if (!installation.is_enabled) return null;
    const ids = installation.department_ids || [];
    if (ids.length === 0) return 'Installed · Org-wide';
    const names = ids.map((id) => deptNameById[id]).filter(Boolean);
    if (names.length === 0) return `Installed · ${ids.length} dept${ids.length === 1 ? '' : 's'}`;
    if (names.length <= 2) return `Installed · ${names.join(', ')}`;
    return `Installed · ${names.slice(0, 2).join(', ')} +${names.length - 2}`;
  }

  async function doGrant(entry) {
    if (!org) return;
    setBusyType(entry.type);
    try {
      await api('/platform/agents/grant', {
        method: 'POST',
        body: { org_id: org.id, type: entry.type },
      });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyType(null);
    }
  }

  async function doRevoke(entry, installation) {
    if (!org) return;
    const willUninstall = !!installation?.is_enabled;
    const niceName = entry.display_name || entry.name;
    const ok = await confirm({
      title: `Revoke ${niceName} from ${org.name}?`,
      message:
        (willUninstall
          ? 'The org admin currently has this installed \u2014 revoking will uninstall it immediately and members will lose access.\n\n'
          : '')
        + 'Any department scoping chosen by the org admin will be preserved if you re-grant later.',
      confirmLabel: 'Revoke',
      destructive: true,
    });
    if (!ok) return;

    setBusyType(entry.type);
    try {
      await api('/platform/agents/revoke', {
        method: 'POST',
        body: { org_id: org.id, type: entry.type },
      });
      toast(`${niceName} revoked from ${org.name}.`, { variant: 'success' });
      await load();
    } catch (e) {
      setErr(e.message);
    } finally {
      setBusyType(null);
    }
  }

  return (
    <AppShell crumbs={['Platform', 'Agents']}>
      <div style={{ marginBottom: 22 }}>
        <h1 className="page-title" style={{ marginBottom: 4 }}>
          Platform <em>agents</em>
        </h1>
        <p className="page-subtitle" style={{ marginBottom: 0 }}>
          Pick an organisation to see what's granted. Granting an agent makes it
          appear in the org admin's Agent Library — they decide whether to install
          it and which departments can see it.
        </p>
      </div>

      {err && <div className="inv-warning" style={{ marginBottom: 14 }}>{err}</div>}

      {/* Org picker */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)', padding: '16px 18px',
        display: 'flex', alignItems: 'center', gap: 14, marginBottom: 22,
        flexWrap: 'wrap',
      }}>
        <div style={{
          fontSize: 11, color: 'var(--ink-muted)',
          letterSpacing: '0.06em', textTransform: 'uppercase',
        }}>
          Organisation
        </div>
        {org && <OrgThumb org={org} size={28} />}
        <select
          value={orgId ?? ''}
          onChange={(e) => setOrgId(Number(e.target.value))}
          disabled={loading || orgs.length === 0}
          style={{
            flex: 1, minWidth: 220,
            background: 'var(--bg)', border: '1px solid var(--border-strong)',
            color: 'var(--ink)', padding: '8px 10px', borderRadius: 4,
            fontSize: 14, outline: 'none',
          }}
        >
          {orgs.length === 0 && <option value="">No organisations yet</option>}
          {orgs.map((o) => (
            <option key={o.id} value={o.id}>{o.name}</option>
          ))}
        </select>
        {org && (
          <div style={{ fontSize: 12, color: 'var(--ink-dim)' }}>
            <span style={{ color: 'var(--ink)' }}>{granted.length}</span> granted
            {' · '}
            <span style={{ color: 'var(--ink)' }}>{notGranted.filter(g => g.entry.implemented).length}</span> available to grant
          </div>
        )}
      </div>

      {loading ? (
        <div className="empty">Loading…</div>
      ) : !org ? (
        <div className="empty">Create an organisation first from the Organizations page.</div>
      ) : (
        <>
          {/* Granted section */}
          <div className="section-header">
            <h2>Granted <em>— {granted.length}</em></h2>
          </div>
          {granted.length === 0 ? (
            <div className="empty" style={{ marginBottom: 26 }}>
              No agents granted yet. Pick some from the "Not granted" list below.
            </div>
          ) : (
            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)', marginBottom: 26, overflow: 'hidden',
            }}>
              {granted.map(({ entry, installation }, idx) => (
                <div
                  key={entry.type}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 14,
                    padding: '14px 18px',
                    borderBottom: idx === granted.length - 1 ? 0 : '1px solid var(--border)',
                  }}
                >
                  <AgentIcon name={entry.icon} size={32} />
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ color: 'var(--ink)', fontWeight: 600, fontSize: 15, fontFamily: 'var(--serif)' }}>
                      {entry.display_name || entry.name}
                      {entry.display_name && entry.display_name !== entry.name && (
                        <span style={{
                          marginLeft: 8,
                          color: 'var(--ink-muted)',
                          fontSize: 11,
                          fontFamily: 'var(--sans)',
                          fontWeight: 500,
                          letterSpacing: '0.02em',
                        }}>
                          {entry.name}
                        </span>
                      )}
                    </div>
                    <div style={{ color: 'var(--ink-muted)', fontSize: 12, marginTop: 2 }}>
                      {entry.category || '—'}
                      {installation?.is_enabled && (
                        <>
                          <span style={{ margin: '0 8px', color: 'var(--border)' }}>·</span>
                          <span style={{ color: 'var(--accent)' }}>
                            {scopeLabel(installation)}
                          </span>
                        </>
                      )}
                      {installation && !installation.is_enabled && (
                        <>
                          <span style={{ margin: '0 8px', color: 'var(--border)' }}>·</span>
                          <span style={{ color: 'var(--ink-dim)' }}>
                            Not yet installed by org admin
                          </span>
                        </>
                      )}
                    </div>
                  </div>
                  <button
                    className="btn"
                    onClick={() => doRevoke(entry, installation)}
                    disabled={busyType === entry.type}
                  >
                    {busyType === entry.type ? 'Revoking…' : 'Revoke'}
                  </button>
                </div>
              ))}
            </div>
          )}

          {/* Not granted section */}
          <div className="section-header">
            <h2>Not granted <em>— {notGranted.length}</em></h2>
          </div>
          {notGranted.length === 0 ? (
            <div className="empty">Every catalog agent has been granted to this org.</div>
          ) : (
            <div style={{
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              borderRadius: 'var(--radius-lg)', overflow: 'hidden',
            }}>
              {notGranted.map(({ entry }, idx) => {
                const disabled = !entry.implemented || busyType === entry.type;
                return (
                  <div
                    key={entry.type}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: '14px 18px',
                      borderBottom: idx === notGranted.length - 1 ? 0 : '1px solid var(--border)',
                      opacity: entry.implemented ? 1 : 0.55,
                    }}
                  >
                    <AgentIcon name={entry.icon} size={32} />
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ color: 'var(--ink)', fontWeight: 600, fontSize: 15, fontFamily: 'var(--serif)' }}>
                        {entry.display_name || entry.name}
                        {entry.display_name && entry.display_name !== entry.name && (
                          <span style={{
                            marginLeft: 8,
                            color: 'var(--ink-muted)',
                            fontSize: 11,
                            fontFamily: 'var(--sans)',
                            fontWeight: 500,
                            letterSpacing: '0.02em',
                          }}>
                            {entry.name}
                          </span>
                        )}
                        {!entry.implemented && (
                          <span className="cap-tag" style={{ marginLeft: 8, verticalAlign: 'middle', fontFamily: 'var(--sans)' }}>
                            Coming soon
                          </span>
                        )}
                      </div>
                      <div style={{ color: 'var(--ink-muted)', fontSize: 12, marginTop: 2 }}>
                        {entry.category || '—'}
                        {entry.tagline && (
                          <>
                            <span style={{ margin: '0 8px', color: 'var(--border)' }}>·</span>
                            <span>{entry.tagline}</span>
                          </>
                        )}
                      </div>
                    </div>
                    <button
                      className="btn btn-primary"
                      onClick={() => doGrant(entry)}
                      disabled={disabled}
                      title={!entry.implemented ? 'Not yet available on the platform' : ''}
                    >
                      {busyType === entry.type ? 'Granting…' : '+ Grant'}
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </AppShell>
  );
}
