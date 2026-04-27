import { useEffect, useState } from 'react';
import { Link, useLocation, useParams } from 'react-router-dom';
import AppShell from '../components/AppShell.jsx';
import AgentIcon from '../components/AgentIcon.jsx';
import { LoadingBlock } from '../components/Loading.jsx';
import DMAAgentPage from './DMAAgentPage.jsx';
import { api } from '../lib/api.js';

const DMA_TYPES = new Set([
  'data_classifier', 'master_builder', 'data_enrichment',
  'group_duplicates', 'lookup_agent',
]);

export default function AgentDetailPage() {
  const { type } = useParams();
  const location = useLocation();
  // Prefer the agent payload passed via <Link state> to avoid a round-trip.
  const [agent, setAgent] = useState(location.state?.agent || null);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (agent) return;
    api('/agents')
      .then((list) => {
        const match = list.find((a) => a.type === type);
        if (!match) setErr('Agent not found or you do not have access.');
        else setAgent(match);
      })
      .catch((e) => setErr(e.message));
  }, [type, agent]);

  // Delegate to the DMAhub pipeline UI for ported agents. Same delegation
  // pattern Investigation uses — gives DMA its own page without needing
  // its own route blocks, and keeps useParams() working.
  if (DMA_TYPES.has(type)) {
    return <DMAAgentPage agentType={type} agent={agent} />;
  }

  return (
    <AppShell crumbs={['Agent Hub', agent?.name || type]}>
      {err && <div className="inv-warning">{err}</div>}
      {!err && !agent && <LoadingBlock text="Loading agent…" />}
      {agent && (
        <>
          <div style={{ display: 'flex', gap: 20, alignItems: 'flex-start' }}>
            <div className="agent-icon" style={{ width: 56, height: 56 }}>
              <AgentIcon name={agent.icon || 'chart'} size={28} />
            </div>
            <div style={{ flex: 1 }}>
              <h1 className="page-title">{agent.name}</h1>
              <div className="page-subtitle">{agent.tagline}</div>
              <div className="agent-meta" style={{ marginBottom: 16 }}>
                <span className="cap-tag cap-tag--accent">{agent.category}</span>
                {agent.departments.map((d) => (
                  <span key={d.id} className="cap-tag">{d.name}</span>
                ))}
              </div>
            </div>
            <Link to="/" className="btn">← Back</Link>
          </div>

          {/* L4: previously said "Agent workspace coming next" which reads like
              a promise with a date. The catalog entry gives useful metadata
              (tagline, category, dept scope), so we keep that and shorten the
              disclaimer to "not available yet" — honest about the state. */}
          <div className="empty" style={{ marginTop: 32 }}>
            <div style={{ fontFamily: 'var(--sans)', fontWeight: 800, fontSize: 22, letterSpacing: '-0.02em', marginBottom: 8 }}>
              Not available yet
            </div>
            <div style={{ fontSize: 13 }}>
              <b>{agent.name}</b> is in the catalog but doesn't have a workspace
              on this build. Check the Agent Library for agents you can use today.
            </div>
          </div>
        </>
      )}
    </AppShell>
  );
}
