import { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import AppShell from '../components/AppShell.jsx';
import AgentIcon from '../components/AgentIcon.jsx';
import TemplatePreview from '../components/TemplatePreview.jsx';
import { api, apiForm, downloadFile } from '../lib/api.js';

const AGENT_TYPE = 'rca_investigation';

const PHASE_LABELS = {
  intake: 'Intake',
  gap_analysis: 'Gap analysis',
  targeted_qa: 'Targeted Q&A',
  drafting: 'Drafting',
  review: 'Review',
  complete: 'Complete',
};

function splitWarnings(reply) {
  if (!reply) return { text: '', warnings: [] };
  const parts = reply.split(/\n\n+/);
  const body = [];
  const warnings = [];
  for (const p of parts) {
    const m = /^SOP Note:\s*(.*)$/s.exec(p);
    if (m) warnings.push(m[1].trim()); else body.push(p);
  }
  return { text: body.join('\n\n').trim(), warnings };
}

function timeOfDay(iso) {
  if (!iso) return '';
  try { return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }
  catch { return ''; }
}

export default function InvestigationPage({ agent: agentProp }) {
  const navigate = useNavigate();
  const { runId: runIdParam } = useParams();

  // Agent metadata — per-org Agent row. Resolve by type inside the current
  // org context; do NOT hardcode the numeric id (Syngene's is 11, Uniqus is
  // 27, etc). `agentId` is used for every subsequent API call.
  const [agent, setAgent] = useState(agentProp || null);
  const agentId = agent?.id ?? null;
  useEffect(() => {
    if (agent) return;
    api('/agents?scope=installed')
      .then((list) => setAgent(list.find((a) => a.type === AGENT_TYPE) || null))
      .catch(() => {});
  }, [agent]);

  // Run state — `runId` is the tail of the current chain.
  const [runId, setRunId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [fields, setFields] = useState({});
  const [coveragePct, setCoveragePct] = useState(0);
  const [phase, setPhase] = useState('intake');
  const [runs, setRuns] = useState([]);

  // Input state.
  const [text, setText] = useState('');
  const [files, setFiles] = useState([]);

  // UX state.
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');

  const fileInputRef = useRef(null);
  const convRef = useRef(null);

  const hasContent = messages.length > 0 || Object.values(fields).some((f) => f?.value);

  // Runs list for the history strip.
  const refreshRuns = () => {
    if (!agentId) return;
    api(`/agents/${agentId}/runs`)
      .then(setRuns)
      .catch((e) => console.warn('could not load runs:', e.message));
  };
  useEffect(refreshRuns, [agentId]);

  // Deep-link: /agents/rca_investigation/chat/:runId preloads that run's chain.
  useEffect(() => {
    if (!runIdParam) return;
    const id = Number(runIdParam);
    if (Number.isNaN(id) || id === runId) return;
    api(`/runs/${id}`)
      .then(loadRunIntoUI)
      .catch((e) => setErr(`Could not load run ${id}: ${e.message}`));
    // Intentionally only re-run when the URL param changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runIdParam]);

  // Scroll chat to bottom on new messages or while thinking.
  useEffect(() => {
    if (convRef.current) convRef.current.scrollTop = convRef.current.scrollHeight;
  }, [messages, busy]);

  function loadRunIntoUI(run) {
    const out = run.output || {};
    const session = out.session || {};
    setRunId(run.id);
    setMessages(session.messages || []);
    setFields(session.fields || {});
    setCoveragePct(out.coverage_pct || 0);
    setPhase(out.phase || 'intake');
  }

  function startNew() {
    setRunId(null);
    setMessages([]);
    setFields({});
    setCoveragePct(0);
    setPhase('intake');
    setErr('');
    setText('');
    setFiles([]);
    // Drop any :runId from the URL so the chat resets cleanly.
    if (runIdParam) navigate('/agents/rca_investigation/chat');
  }

  async function loadRunById(id) {
    try {
      const run = await api(`/runs/${id}`);
      loadRunIntoUI(run);
    } catch (e) {
      setErr(`Could not load run ${id}: ${e.message}`);
    }
  }

  function onFilesPicked(e) {
    const picked = Array.from(e.target.files || []);
    setFiles((prev) => [...prev, ...picked]);
    if (fileInputRef.current) fileInputRef.current.value = '';
  }

  function removeFile(idx) {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
  }

  async function submit() {
    if (busy) return;
    const textToSend = text.trim();
    const filesToSend = files;
    if (!textToSend && filesToSend.length === 0) return;

    // Clear input immediately — the request is in flight, don't wait.
    setText('');
    setFiles([]);
    setErr('');
    setBusy(true);

    const optimistic = {
      id: `__optim_${Date.now()}`,
      role: 'user',
      content: textToSend,
      timestamp: new Date().toISOString(),
      attachments: filesToSend.map((f) => ({ filename: f.name, size: f.size, content_type: f.type })),
    };
    setMessages((prev) => [...prev, optimistic]);

    const form = new FormData();
    form.append('message', textToSend);
    if (runId != null) form.append('parent_run_id', String(runId));
    for (const f of filesToSend) form.append('files', f);

    if (!agentId) {
      setErr('Investigation agent is not installed in this organisation.');
      setBusy(false);
      return;
    }
    try {
      let run;
      try {
        run = await apiForm(`/agents/${agentId}/run`, form);
      } catch (e) {
        if (e.message === 'parse_error') {
          console.warn('POST /run JSON parse failed; fetching via /runs list');
          const latest = await api(`/agents/${agentId}/runs`);
          if (!latest.length) throw new Error('Run started but could not be found');
          run = await api(`/runs/${latest[0].id}`);
        } else {
          throw e;
        }
      }
      loadRunIntoUI(run);
      refreshRuns();
    } catch (e) {
      setErr(e.message || 'Run failed');
      setMessages((prev) => prev.filter((m) => m.id !== optimistic.id));
    } finally {
      setBusy(false);
    }
  }

  async function onFieldEdit(fieldId, newValue) {
    // Inline edits go through PATCH /api/runs/{id}/fields/{field_id}.
    // Local state updates optimistically; on error we roll back.
    const prevField = fields[fieldId];
    const optimisticField = {
      ...(prevField || { label: fieldId, status: 'empty', section: '' }),
      value: newValue,
      status: newValue.trim() ? 'filled' : 'empty',
      last_edited_by: 'user',
    };
    setFields((prev) => ({ ...prev, [fieldId]: optimisticField }));
    setErr('');

    if (!runId) {
      // No run yet — create a stub new run locally. We only persist when the
      // user actually sends a message or the field will vanish on reload.
      // Simplest UX: require at least one AI run before field edits persist.
      setErr('Send a message or upload a file first — fields start from the AI draft.');
      setFields((prev) => ({ ...prev, [fieldId]: prevField || { value: '', status: 'empty' } }));
      return;
    }

    try {
      const run = await api(`/runs/${runId}/fields/${fieldId}`, {
        method: 'PATCH',
        body: { value: newValue },
      });
      loadRunIntoUI(run);
      refreshRuns();
    } catch (e) {
      // Roll back.
      setFields((prev) => ({ ...prev, [fieldId]: prevField }));
      setErr(`Edit failed: ${e.message}`);
    }
  }

  async function downloadDocx() {
    if (!runId) return;
    try {
      await downloadFile(`/runs/${runId}/export.docx`, `Investigation_${runId}.docx`);
    } catch (e) {
      setErr(`Export failed: ${e.message}`);
    }
  }

  function onKeyDown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      submit();
    }
  }

  const recentRuns = useMemo(() => runs.slice(0, 10), [runs]);
  const isEdit = (r) => r.status === 'completed' && r.duration_ms === 0;

  return (
    <AppShell crumbs={['Agent Hub', agent?.name || 'Investigation']}>
      <div className="inv-workspace">
        {/* Header */}
        <div className="inv-header">
          <div className="agent-icon" style={{ width: 44, height: 44 }}>
            <AgentIcon name={agent?.icon || 'search'} size={22} />
          </div>
          <div>
            {/* Short brand name primary, long name as subtitle. Falls back
                to the hardcoded strings only during initial load. */}
            <div className="inv-header-title">
              {agent?.display_name || agent?.name || 'Devio'}
            </div>
            {agent?.display_name && agent.display_name !== agent.name && (
              <div
                style={{
                  fontSize: 11,
                  color: 'var(--ink-muted)',
                  letterSpacing: '0.02em',
                  fontWeight: 500,
                  marginTop: 1,
                }}
              >
                {agent.name}
              </div>
            )}
            <div className="inv-header-sub">
              {agent?.tagline || 'Deviation intake, root-cause analysis, and investigation report drafting.'}
            </div>
            <div className="inv-header-chips">
              {(agent?.departments || []).map((d) => (
                <span key={d.id} className="cap-tag">{d.name}</span>
              ))}
              <span className="inv-pill inv-pill--accent">
                Coverage <strong>{Number(coveragePct).toFixed(1)}%</strong>
              </span>
              <span className="inv-pill">
                Phase <strong>{PHASE_LABELS[phase] || phase}</strong>
              </span>
            </div>
          </div>
          <div className="inv-header-actions">
            <Link to="/agents/rca_investigation" className="btn">← Dashboard</Link>
            <button className="btn" onClick={downloadDocx} disabled={!hasContent || !runId || busy}>
              Download Report (.docx)
            </button>
            <button className="btn" onClick={startNew} disabled={busy}>
              New Investigation
            </button>
          </div>
        </div>

        {/* History strip */}
        {recentRuns.length > 0 && (
          <div className="inv-runs">
            <span className="inv-runs-label">History</span>
            {recentRuns.map((r) => {
              const label = r.investigation_no ?? r.id;
              return (
                <button
                  key={r.id}
                  type="button"
                  className={`inv-run-chip${r.id === runId ? ' active' : ''}`}
                  onClick={() => loadRunById(r.id)}
                  title={`Investigation #${label} · ${r.coverage_pct ?? 0}% · ${r.phase || 'intake'}${isEdit(r) ? ' · edit' : ''}`}
                >
                  #{label} · {Number(r.coverage_pct ?? 0).toFixed(0)}%
                  {isEdit(r) && <span className="inv-run-chip-edit">edit</span>}
                </button>
              );
            })}
          </div>
        )}

        {/* Two-pane body */}
        <div className="inv-body">
          {/* Left: chat */}
          <div className="inv-pane">
            <div className="inv-pane-header">
              <span>Conversation</span>
              <span>{messages.length} turn{messages.length === 1 ? '' : 's'}</span>
            </div>
            <div className="inv-conv" ref={convRef}>
              {messages.length === 0 && !busy && (
                <div className="inv-empty-conv">
                  <div className="inv-empty-conv-icon">
                    <AgentIcon name="search" size={24} />
                  </div>
                  <h2 className="inv-empty-conv-title">Describe the deviation</h2>
                  <p className="inv-empty-conv-body">
                    Include dates, equipment, people, what went wrong, and the immediate actions taken.
                    The agent drafts the FORM-GMP-QA-0504 sections from what you provide and asks follow-up
                    questions for anything it needs.
                  </p>
                  <div className="inv-empty-conv-hints">
                    {[
                      // Generic GMP deviation examples — previously referenced
                      // a Syngene-specific system name (EDMS) and a narrow
                      // equipment context ("CIP conductivity on bioreactor").
                      // Kept cross-tenant-usable but still sector-relevant so
                      // a pharma user recognises them.
                      'Clean-in-place deviation during a batch',
                      'Temperature excursion in cold storage',
                      'Document-management system downtime affecting release',
                      'Equipment calibration out of tolerance',
                    ].map((hint) => (
                      <button
                        key={hint}
                        type="button"
                        className="inv-hint-chip"
                        onClick={() => setText(hint)}
                      >
                        {hint}
                      </button>
                    ))}
                  </div>
                </div>
              )}
              {messages.map((m) => {
                const { text: body, warnings } = m.role === 'agent'
                  ? splitWarnings(m.content)
                  : { text: m.content, warnings: [] };
                return (
                  <div key={m.id} className={`inv-msg inv-msg--${m.role}`}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div className="inv-msg-role">
                        {m.role === 'user' ? 'You' : 'Devio'} · {timeOfDay(m.timestamp)}
                      </div>
                      <div className="inv-msg-bubble">{body || '(no reply text)'}</div>
                      {m.attachments?.length > 0 && (
                        <div className="inv-msg-attachments">
                          {m.attachments.map((a, i) => (
                            <span key={i} className="inv-msg-attachment">📎 {a.filename}</span>
                          ))}
                        </div>
                      )}
                      {warnings.map((w, i) => (
                        <div key={i} className="inv-warning">SOP: {w}</div>
                      ))}
                    </div>
                  </div>
                );
              })}
              {busy && (
                <div className="inv-thinking">
                  <span className="spinner" />
                  <span>Working through the two-phase pipeline<span className="inv-thinking-dots" /></span>
                </div>
              )}
            </div>

            {/* Input row */}
            <div className="inv-input">
              <div className="inv-input-row">
                <textarea
                  placeholder={hasContent
                    ? 'Add more context or correct a section…'
                    : 'Describe the deviation. Include PR#, department, initiator, timeline…'}
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  onKeyDown={onKeyDown}
                  disabled={busy}
                />
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  <button
                    type="button"
                    className="btn"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={busy}
                    title="Attach PDF / DOCX / DOC / TXT"
                  >
                    📎 Attach
                  </button>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={submit}
                    disabled={busy || (!text.trim() && files.length === 0)}
                    style={{ minWidth: 90, justifyContent: 'center' }}
                  >
                    {busy ? 'Running…' : 'Send'}
                  </button>
                  <input
                    ref={fileInputRef}
                    type="file"
                    multiple
                    accept=".pdf,.doc,.docx,.txt,.csv,.log"
                    onChange={onFilesPicked}
                    style={{ display: 'none' }}
                  />
                </div>
              </div>
              {files.length > 0 && (
                <div className="inv-attach-row">
                  <span>Attached:</span>
                  {files.map((f, i) => (
                    <span key={i} className="inv-attach-chip">
                      {f.name}
                      <button type="button" onClick={() => removeFile(i)} title="Remove">×</button>
                    </span>
                  ))}
                </div>
              )}
              {err && <div className="inv-warning">{err}</div>}
              <div style={{ fontSize: 10, color: 'var(--ink-muted)', letterSpacing: '0.04em' }}>
                {/* L3: previously leaked the underlying model ("GPT-5.3") to
                    end users. Hide the model identity; keep the wait hint. */}
                ⌘/Ctrl + Enter to send · each turn typically takes 60–80 seconds
              </div>
            </div>
          </div>

          {/* Right: live template preview */}
          <div className="inv-pane">
            <div className="inv-pane-header">
              <span>FORM-GMP-QA-0504 · Live draft</span>
              <span>Click any field to edit</span>
            </div>
            <TemplatePreview fields={fields} busy={busy} onEdit={onFieldEdit} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
