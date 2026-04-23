import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { api } from '../lib/api.js';
import { useAuth } from '../lib/auth.jsx';

const WELCOME = {
  role: 'assistant',
  content:
    "Hi \u2014 ask me anything about the platform. Agents, roles, integrations, dashboards \u2014 I\u2019ll point you to the right place.",
};

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
  const { user, isAuthenticated } = useAuth();
  const [open, setOpen] = useState(false);
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

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    setErr('');
    const nextMessages = [...messages, { role: 'user', content: text }];
    setMessages(nextMessages);
    setInput('');
    setBusy(true);

    try {
      // Send only the last ~8 turns so the payload stays small.
      const tail = nextMessages.slice(-8);
      const res = await api('/assistant/chat', {
        method: 'POST',
        body: { messages: tail.map((m) => ({ role: m.role, content: m.content })) },
      });
      const updated = [...nextMessages, { role: 'assistant', content: res.reply }];
      setMessages(updated);
      saveHistory(user?.id, updated);
    } catch (e) {
      setErr(e.message || 'Assistant is unavailable');
      // Keep the user's message in the UI but don't persist a failed turn
      // as an assistant reply — next attempt should resend fresh.
    } finally {
      setBusy(false);
    }
  }, [input, busy, messages, user?.id]);

  function clear() {
    setMessages([WELCOME]);
    saveHistory(user?.id, [WELCOME]);
    setErr('');
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
    // Keep code blocks compact inside the chat bubble.
    code: ({ inline, children, ...props }) =>
      inline ? (
        <code {...props}>{children}</code>
      ) : (
        <pre><code {...props}>{children}</code></pre>
      ),
  }), []);

  if (!isAuthenticated) return null;

  return (
    <>
      <button
        type="button"
        className={`assistant-fab${open ? ' assistant-fab--open' : ''}`}
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Close assistant' : 'Open assistant'}
        title={open ? 'Close assistant' : 'Ask the platform assistant'}
      >
        {open ? (
          // Close state — simple chevron-down, reads as "collapse".
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M6 9l6 6 6-6" />
          </svg>
        ) : (
          // Chat-bubble with sparkle — "assistant" imagery instead of the
          // generic "?" which read as a help-tip rather than a conversation.
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M21 12a8 8 0 0 1-11.6 7.13L4 20l1-4.4A8 8 0 1 1 21 12z" />
            <path d="M12 8.5v3" />
            <path d="M10.5 10h3" />
          </svg>
        )}
      </button>

      <aside className={`assistant-panel${open ? ' assistant-panel--open' : ''}`} aria-hidden={!open}>
        <header className="assistant-header">
          <div>
            <div className="assistant-title">Platform assistant</div>
            <div className="assistant-sub">Ask me about the hub — agents, roles, integrations.</div>
          </div>
          <button type="button" className="link-btn" onClick={clear} title="Clear conversation">
            Clear
          </button>
        </header>

        <div className="assistant-conv" ref={bottomRef}>
          {messages.map((m, i) => (
            <div key={i} className={`assistant-msg assistant-msg--${m.role}`}>
              <div className="assistant-msg-role">
                {m.role === 'user' ? 'You' : 'Assistant'}
              </div>
              <div className="assistant-msg-bubble">
                {m.role === 'assistant'
                  ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={markdownComponents}>{m.content}</ReactMarkdown>
                  : m.content}
              </div>
            </div>
          ))}
          {busy && (
            <div className="assistant-msg assistant-msg--assistant">
              <div className="assistant-msg-role">Assistant</div>
              <div className="assistant-msg-bubble">
                <span className="spinner" style={{ marginRight: 8, verticalAlign: -2 }} />
                Thinking<span className="inv-thinking-dots" />
              </div>
            </div>
          )}
          {err && <div className="inv-warning" style={{ marginTop: 8 }}>{err}</div>}
        </div>

        <footer className="assistant-input">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask anything about the platform…"
            rows={2}
            disabled={busy}
          />
          <button
            type="button"
            className="btn btn-primary"
            onClick={send}
            disabled={busy || !input.trim()}
          >
            {busy ? 'Sending…' : 'Send'}
          </button>
        </footer>
      </aside>
    </>
  );
}
