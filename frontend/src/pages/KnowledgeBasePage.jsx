import AppShell from '../components/AppShell.jsx';

export default function KnowledgeBasePage() {
  return (
    <AppShell crumbs={['Knowledge Base']}>
      <h1 className="page-title">Knowledge Base</h1>
      <p className="page-subtitle">Upload and organize the documents your agents ground on.</p>
      <div className="empty">Coming soon — department-scoped document library with upload, tagging and indexing.</div>
    </AppShell>
  );
}
