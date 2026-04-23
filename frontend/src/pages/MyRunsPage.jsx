import AppShell from '../components/AppShell.jsx';

/**
 * Placeholder. The route still exists so any bookmarked URL renders
 * something sensible, but the page is hidden from the sidebar until
 * the per-user runs feed is implemented (L4 — the previous copy said
 * "No runs yet" which was misleading: nothing was fetched).
 */
export default function MyRunsPage() {
  return (
    <AppShell crumbs={['My Runs']}>
      <h1 className="page-title">My Runs</h1>
      <p className="page-subtitle">A personal feed of every agent run you've triggered.</p>
      <div className="empty">
        Coming soon — until then, each agent's own page (e.g. the Investigation
        Dashboard) lists your runs for that agent.
      </div>
    </AppShell>
  );
}
