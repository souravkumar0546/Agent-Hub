import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { api, getOrgId, getToken, setOrgId, setToken } from './api.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await api('/auth/me');
      setUser(me);
      // Auto-pick an org only for non-super-admins. Super-admins choose
      // explicitly via the Platform → Organizations page so they don't
      // get silently dropped into whichever org happens to be listed first.
      if (me.current_org_id && !getOrgId() && !me.is_super_admin) {
        setOrgId(me.current_org_id);
      }
    } catch {
      setToken(null);
      setOrgId(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email, password) => {
    const data = await api('/auth/login', { method: 'POST', body: { email, password } });
    setToken(data.access_token);
    // Same rule as `refresh`: super-admins skip the auto-select so they
    // land on the platform page with a clean X-Org-Id.
    if (data.user?.current_org_id && !data.user?.is_super_admin) {
      setOrgId(data.user.current_org_id);
    }
    setUser(data.user);
    return data.user;
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setOrgId(null);
    setUser(null);
    // Clear any super-admin "viewing as org" session marker.
    try { sessionStorage.removeItem('sah.asOrg'); } catch (_) { /* ignore */ }
  }, []);

  const switchOrg = useCallback(
    async (orgId) => {
      setOrgId(orgId);
      await refresh();
    },
    [refresh],
  );

  const value = {
    user,
    loading,
    isAuthenticated: !!user,
    isSuperAdmin: user?.is_super_admin || false,
    isOrgAdmin: user?.current_org_role === 'ORG_ADMIN' || user?.is_super_admin || false,
    login,
    logout,
    refresh,
    switchOrg,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
