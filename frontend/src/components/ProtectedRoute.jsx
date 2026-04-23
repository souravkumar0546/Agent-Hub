import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../lib/auth.jsx';

export default function ProtectedRoute({ children, require }) {
  const { isAuthenticated, isSuperAdmin, isOrgAdmin, loading } = useAuth();
  const location = useLocation();

  if (loading) return <div style={{ padding: 40, color: 'var(--ink-dim)' }}>Loading…</div>;
  if (!isAuthenticated) return <Navigate to="/login" state={{ from: location }} replace />;

  if (require === 'super_admin' && !isSuperAdmin) return <Navigate to="/" replace />;
  if (require === 'org_admin' && !isOrgAdmin) return <Navigate to="/" replace />;

  return children;
}
