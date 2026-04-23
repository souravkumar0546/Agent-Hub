import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import AppShell from '../components/AppShell.jsx';
import AgentIcon from '../components/AgentIcon.jsx';
import ClassifyPage from '../dma/pages/ClassifyPage.jsx';
import DataEnrichmentPage from '../dma/pages/DataEnrichmentPage.jsx';
import GroupDuplicatesPage from '../dma/pages/GroupDuplicatesPage.jsx';
import LookupPage from '../dma/pages/LookupPage.jsx';
import MasterBuilderPage from '../dma/pages/MasterBuilderPage.jsx';
import '../dma/styles.css';
import { api } from '../lib/api.js';

// Map agent `type` → DMAhub React page component.
const DMA_PAGES = {
  data_classifier: ClassifyPage,
  master_builder: MasterBuilderPage,
  data_enrichment: DataEnrichmentPage,
  group_duplicates: GroupDuplicatesPage,
  lookup_agent: LookupPage,
};


export default function DMAAgentPage({ agentType, agent: agentProp }) {
  // When delegated to from AgentDetailPage, type + agent come in as props
  // (because the URL route param name is `:type` but this component can
  // also render outside that route). Fall back to URL + fetch when needed.
  const params = useParams();
  const location = useLocation();
  const type = agentType || params.type;
  const [agent, setAgent] = useState(agentProp || location.state?.agent || null);

  useEffect(() => {
    if (agent) return;
    api('/agents').then((list) => {
      setAgent(list.find((a) => a.type === type) || null);
    });
  }, [type, agent]);

  const Page = DMA_PAGES[type];
  if (!Page) {
    return (
      <AppShell crumbs={['Agent Hub', type]}>
        <div className="empty">Unknown DMAhub agent: {type}</div>
      </AppShell>
    );
  }

  return (
    <AppShell crumbs={['Agent Hub', agent?.name || type]}>
      <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start', marginBottom: 18 }}>
        <div className="agent-icon" style={{ width: 48, height: 48 }}>
          <AgentIcon name={agent?.icon || 'box'} size={24} />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1 className="page-title" style={{ marginBottom: 4 }}>{agent?.name || type}</h1>
          <div className="page-subtitle" style={{ marginBottom: 10 }}>{agent?.tagline}</div>
          <div className="agent-meta">
            <span className="cap-tag cap-tag--accent">{agent?.category || 'Data Management'}</span>
            {(agent?.departments || []).map((d) => (
              <span key={d.id} className="cap-tag">{d.name}</span>
            ))}
          </div>
        </div>
        <Link to="/" className="btn">← Agent Hub</Link>
      </div>

      {/* The ported DMAhub page is rendered into a scoped container so its
          light-theme styles don't affect the surrounding dark shell. */}
      <div className="dma-scope">
        <Page />
      </div>
    </AppShell>
  );
}
