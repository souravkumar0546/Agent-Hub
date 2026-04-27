import { Route, Routes } from 'react-router-dom';
import ProtectedRoute from './components/ProtectedRoute.jsx';
import { useAuth } from './lib/auth.jsx';
import AgentDetailPage from './pages/AgentDetailPage.jsx';
import AgentHubPage from './pages/AgentHubPage.jsx';
import AgentLibraryPage from './pages/AgentLibraryPage.jsx';
import IntegrationsPage from './pages/IntegrationsPage.jsx';
import InvestigationDashboard from './pages/InvestigationDashboard.jsx';
import InvestigationPage from './pages/InvestigationPage.jsx';
import InviteAcceptPage from './pages/InviteAcceptPage.jsx';
import KnowledgeBasePage from './pages/KnowledgeBasePage.jsx';
import LandingPage from './pages/LandingPage.jsx';
import LoginPage from './pages/LoginPage.jsx';
import MyRunsPage from './pages/MyRunsPage.jsx';
import OrgDashboard from './pages/OrgDashboard.jsx';
import PlatformDashboard from './pages/PlatformDashboard.jsx';
import SettingsPage from './pages/SettingsPage.jsx';
import UserGuidePage from './pages/UserGuidePage.jsx';
import AuditLogPage from './pages/admin/AuditLogPage.jsx';
import DepartmentsPage from './pages/admin/DepartmentsPage.jsx';
import MembersPage from './pages/admin/MembersPage.jsx';
import PlatformAgentsPage from './pages/platform/PlatformAgentsPage.jsx';
import PlatformOrgsPage from './pages/platform/PlatformOrgsPage.jsx';

/** Root route — public marketing landing for visitors, in-app hub for
 *  authenticated users. Rendering both off `/` keeps every existing
 *  `to="/"` link in the codebase working without further changes. */
function HomeRoute() {
  const { isAuthenticated, loading } = useAuth();
  if (loading) return <div style={{ padding: 40, color: 'var(--ink-dim)' }}>Loading…</div>;
  return isAuthenticated ? <AgentHubPage /> : <LandingPage />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/invite/:token" element={<InviteAcceptPage />} />

      <Route path="/" element={<HomeRoute />} />
      {/* Investigation agent gets a dashboard-first layout with a chat sub-route. */}
      <Route
        path="/agents/rca_investigation"
        element={
          <ProtectedRoute>
            <InvestigationDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/agents/rca_investigation/chat"
        element={
          <ProtectedRoute>
            <InvestigationPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/agents/rca_investigation/chat/:runId"
        element={
          <ProtectedRoute>
            <InvestigationPage />
          </ProtectedRoute>
        }
      />
      {/* All other agent types: AgentDetailPage decides whether to render
          the DMAhub pipeline UI (for the 5 ported agents) or the stub page. */}
      <Route
        path="/agents/:type"
        element={
          <ProtectedRoute>
            <AgentDetailPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/knowledge"
        element={
          <ProtectedRoute>
            <KnowledgeBasePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/runs"
        element={
          <ProtectedRoute>
            <MyRunsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/guide"
        element={
          <ProtectedRoute>
            <UserGuidePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/library"
        element={
          <ProtectedRoute>
            <AgentLibraryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/dashboard"
        element={
          <ProtectedRoute require="org_admin">
            <OrgDashboard />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/members"
        element={
          <ProtectedRoute require="org_admin">
            <MembersPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/departments"
        element={
          <ProtectedRoute require="org_admin">
            <DepartmentsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/audit"
        element={
          <ProtectedRoute require="org_admin">
            <AuditLogPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/integrations"
        element={
          <ProtectedRoute require="org_admin">
            <IntegrationsPage />
          </ProtectedRoute>
        }
      />

      <Route
        path="/platform/dashboard"
        element={
          <ProtectedRoute require="super_admin">
            <PlatformDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform/orgs"
        element={
          <ProtectedRoute require="super_admin">
            <PlatformOrgsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/platform/agents"
        element={
          <ProtectedRoute require="super_admin">
            <PlatformAgentsPage />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}
