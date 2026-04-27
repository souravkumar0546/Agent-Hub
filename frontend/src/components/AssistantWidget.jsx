import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';
import UniqusMark from './UniqusMark.jsx';

const WELCOME = {
  role: 'assistant',
  content:
    "Hi! Ask me anything about Uniqus Hub. I can help with agents, roles, integrations, and how to get things done.",
};

/** First-message suggestion chips, scoped to what the user can actually do.
 *  Modeled on the "Ask Uniqus" pattern — a few canned questions that show
 *  off what the assistant is good for. Members never see admin-only
 *  prompts ("how to invite a member"), super admins see platform-level
 *  prompts on top of the admin set. */
const SUGGESTIONS_BY_ROLE = {
  MEMBER: [
    'What does Devio (RCA) do?',
    'How do I add an agent to my workspace?',
    'How do I export my report?',
    'Can I edit a field the AI filled?',
  ],
  ORG_ADMIN: [
    'How do I invite a new member?',
    'How do I connect SuccessFactors?',
    'Where is the audit log?',
    'How do I create a department?',
  ],
  SUPER_ADMIN: [
    'How do I onboard a new organisation?',
    'How do I grant an agent to a tenant?',
    'How do I suspend an organisation?',
    'Where do I rotate Azure OpenAI keys?',
  ],
};

function roleLabel({ isSuperAdmin, isOrgAdmin }) {
  if (isSuperAdmin) return 'SUPER_ADMIN';
  if (isOrgAdmin) return 'ORG_ADMIN';
  return 'MEMBER';
}

const PRIVACY_URL = 'https://uniqus.com/privacy-policy';

/** localStorage key for persistence, per-user to avoid cross-account leakage. */
const storageKey = (userId) => `sah.assistant.${userId || 'anon'}`;

function loadHistory(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return [WELCOME];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) && parsed.length ? parsed : [WELCOME];
  } catch {
    return [WELCOME];
  }
}

function saveHistory(userId, messages) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(messages));
  } catch {
    // Quota errors are non-fatal; the chat keeps working in memory.
  }
}


export default function AssistantWidget() {
  const { user, isAuthenticated, isSuperAdmin, isOrgAdmin } = useAuth();
  const role = roleLabel({ isSuperAdmin, isOrgAdmin });
  const suggestions = SUGGESTIONS_BY_ROLE[role] || SUGGESTIONS_BY_ROLE.MEMBER;
  const [open, setOpen] = useState(false);
  // Maximize toggles the panel between regular size (420px wide, 640px tall)
  // and a larger workspace (~90% of viewport). State is local — we don't
  // persist it; users tend to want max for one task and back to normal next.
  const [maxed, setMaxed] = useState(false);
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const bottomRef = useRef(null);
  const inputRef = useRef(null);

  // Load persisted conversation when the user changes.
  useEffect(() => {
    if (!user?.id) return;
    setMessages(loadHistory(user.id));
  }, [user?.id]);

  // Auto-scroll on new messages + auto-focus the input when opened.
  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollTop = bottomRef.current.scrollHeight;
  }, [messages, busy, open]);
  useEffect(() => {
    if (open && inputRef.current) inputRef.current.focus();
  }, [open]);

  const sendText = useCallback(async (text) => {
    const trimmed = (text || '').trim();
    if (!trimmed || busy) return;
    setErr('');
    const nextMessages = [...messages, { role: 'user', content: trimmed }];
    setMessages(nextMessages);
    setInput('');
    setBusy(true);

    try {
      // Send only the last ~8 turns so the payload stays small.
      // The user's role lets the backend tailor the system prompt — e.g.
      // a member asking "how do I invite someone" gets pointed to their
      // admin instead of step-by-step admin instructions.
      const tail = nextMessages.slice(-8);
      const res = await api('/assistant/chat', {
        method: 'POST',
        body: {
          messages: tail.map((m) => ({ role: m.role, content: m.content })),
          user_role: role,
        },
      });
      const updated = [...nextMessages, { role: 'assistant', content: res.reply }];
      setMessages(updated);
      saveHistory(user?.id, updated);
    } catch (e) {
      setErr(e.message || 'Assistant is unavailable');
    } finally {
      setBusy(false);
    }
  }, [busy, messages, role, user?.id]);

  const send = useCallback(() => sendText(input), [sendText, input]);

  function clear() {
    setMessages([WELCOME]);
    saveHistory(user?.id, [WELCOME]);
    setErr('');
  }

  function minimize() {
    setOpen(false);
  }

  function toggleMaxed() {
    setMaxed((v) => !v);
  }

  function onKeyDown(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault();
      send();
    }
    if (e.key === 'Enter' && !e.shiftKey && !e.metaKey && !e.ctrlKey) {
      e.preventDefault();
      send();
    }
  }

  const markdownComponents = useMemo(() => ({
    code: ({ inline, children, ...props }) =>
      inline ? (
        <code {...props}>{children}</code>
      ) : (
        <pre><code {...props}>{children}</code></pre>
      ),
    a: ({ children, ...props }) => (
      <a {...props} target="_blank" rel="noreferrer">{children}</a>
    ),
  }), []);

  if (!isAuthenticated) return null;

  // Show suggestion chips only on the welcome screen (one assistant turn,
  // no user has typed yet). Mirrors the "Ask Uniqus" first-load behaviour.
  const showSuggestions = messages.length === 1 && !busy;

  return (
    <>
      {/* The FAB is only rendered when the panel is closed. When open, the
          header's minimize/close buttons handle dismiss — preventing the
          two-X-buttons confusion users have otherwise. */}
      {!open && (
        <button
          type="button"
          className="assistant-fab"
          onClick={() => setOpen(true)}
          aria-label="Open Ask Uniqus Hub"
          title="Ask Uniqus Hub"
        >
          <span className="assistant-fab-mark" aria-hidden="true">
            <UniqusMark size={26} />
          </span>
          <span className="assistant-fab-label">Ask Uniqus</span>
        </button>
      )}

      <aside
        className={`assistant-panel${open ? ' assistant-panel--open' : ''}${maxed ? ' assistant-panel--max' : ''}`}
        aria-hidden={!open}
      >
        <header className="assistant-header">
          <div className="assistant-header-mark" aria-hidden="true">
            <UniqusMark size={20} />
          </div>
          <div className="assistant-header-text">
            <div className="assistant-title">Ask Uniqus Hub</div>
            <div className="assistant-sub">
              <span className="assistant-status-dot" aria-hidden="true" />
              Help bot · reads from the user guide
            </div>
          </div>
          <div className="assistant-header-actions">
            {/* Clear conversation — trash icon. Sits leftmost so it's
                clearly destructive vs the layout-only buttons. */}
            <button
              type="button"
              className="assistant-icon-btn"
              onClick={clear}
              disabled={busy || messages.length <= 1}
              title="Clear conversation"
              aria-label="Clear conversation"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 6h18M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6M10 11v6M14 11v6" />
              </svg>
            </button>
            {/* Maximize / Restore — two-headed arrow / corner-out vs
                corner-in depending on state. */}
            <button
              type="button"
              className="assistant-icon-btn"
              onClick={toggleMaxed}
              title={maxed ? 'Restore' : 'Maximize'}
              aria-label={maxed ? 'Restore' : 'Maximize'}
            >
              {maxed ? (
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M9 4v5H4M15 4v5h5M9 20v-5H4M15 20v-5h5" />
                </svg>
              ) : (
                <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5" />
                </svg>
              )}
            </button>
            {/* Minimize — collapses panel back to FAB. Conversation persists. */}
            <button
              type="button"
              className="assistant-icon-btn"
              onClick={minimize}
              title="Minimize"
              aria-label="Minimize"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 18h14" />
              </svg>
            </button>
          </div>
        </header>

        <div className="assistant-conv" ref={bottomRef}>
          {messages.map((m, i) => (
            <div key={i} className={`assistant-msg assistant-msg--${m.role}`}>
              <div className="assistant-msg-bubble">
                {m.role === 'assistant'
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{m.content}</ReactMarkdown>
                  : m.content}
              </div>
            </div>
          ))}
          {busy && (
            <div className="assistant-msg assistant-msg--assistant">
              <div className="assistant-msg-bubble assistant-msg-bubble--typing">
                <span className="assistant-typing-dot" />
                <span className="assistant-typing-dot" />
                <span className="assistant-typing-dot" />
              </div>
            </div>
          )}

          {showSuggestions && (
            <div className="assistant-suggestions" role="group" aria-label="Suggested questions">
              {suggestions.map((q) => (
                <button
                  key={q}
                  type="button"
                  className="assistant-chip"
                  onClick={() => sendText(q)}
                  disabled={busy}
                >
                  {q}
                </button>
              ))}
            </div>
          )}

          {err && <div className="inv-warning" style={{ marginTop: 8 }}>{err}</div>}
        </div>

        <footer className="assistant-input">
          <div className="assistant-input-pill">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onKeyDown}
              placeholder="Ask anything about Uniqus Hub…"
              rows={1}
              disabled={busy}
            />
            <button
              type="button"
              className="assistant-send-btn"
              onClick={send}
              disabled={busy || !input.trim()}
              aria-label="Send"
              title="Send (Enter)"
            >
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M5 12h14M13 5l7 7-7 7" />
              </svg>
            </button>
          </div>
          <div className="assistant-foot-row">
            <a
              className="assistant-foot-link"
              href={PRIVACY_URL}
              target="_blank"
              rel="noreferrer"
            >
              Privacy
            </a>
            <span className="assistant-foot-brand">Powered by Uniqus</span>
          </div>
        </footer>
      </aside>
    </>
  );
}
