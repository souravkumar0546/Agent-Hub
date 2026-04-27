import { Link } from 'react-router-dom';
import UniqusMark from '../components/UniqusMark.jsx';
import { useAuth } from '../lib/auth.jsx';

/**
 * Public marketing landing page — what the world sees at `uniquslabs.com/`
 * before they sign in. Modeled on Uniqus Exchange and Uniqus National Office:
 * fixed top nav, gradient hero, three featured agents, numbered "how it
 * works" rail, big stat callouts, footer. Restraint-led, no carousel chrome,
 * the only goal of the page is to get the user to "Sign in".
 */

const FEATURED_AGENTS = [
  {
    name: 'Devio',
    long: 'RCA / Investigation',
    tagline: 'Compliance-grade RCA reports in under 60 minutes — every fact cited to its SOP, exportable to DOCX.',
    badge: '~60 min · cited',
  },
  {
    name: 'Curator',
    long: 'Data Classifier',
    tagline: 'Classify thousands of new records against your taxonomy in minutes — every decision reviewable.',
    badge: 'minutes per 1k rows',
  },
  {
    name: 'Forge',
    long: 'Master Builder',
    tagline: 'Clean master datasets from messy classifications — line-by-line review, full audit log.',
    badge: 'reviewable · audit-trailed',
  },
  {
    name: 'Echo',
    long: 'Data Enrichment',
    tagline: 'Enrich every record with attributes from external sources — provenance kept, never silently overwritten.',
    badge: 'sourced · attributed',
  },
  {
    name: 'Twin',
    long: 'Group Duplicates',
    tagline: 'Find duplicates and near-duplicates across columns — AI-filtered for variants, reviewer-confirmed.',
    badge: 'variants caught',
  },
  {
    name: 'Sonar',
    long: 'Lookup Agent',
    tagline: 'Per-column similarity scoring with a weighted verdict — defensible match decisions on every row.',
    badge: 'weighted verdict',
  },
];

const STEPS = [
  {
    n: '01',
    title: 'Sign in with your work email',
    body: 'Email-first flow resolves your tenant before you ever type a password — no account-picker confusion.',
  },
  {
    n: '02',
    title: 'Pick agents into your workspace',
    body: 'Sixteen purpose-built agents in the library. Add only the ones you actually use.',
  },
  {
    n: '03',
    title: 'Run an agent',
    body: 'Every agent is multi-turn, source-cited, and reviewable. Edit any AI-filled field; the agent never overwrites your edits silently.',
  },
  {
    n: '04',
    title: 'Export or hand off',
    body: 'Download as DOCX, copy to your team, or jump back into the conversation tomorrow — sessions persist.',
  },
];

const STATS = [
  { value: '16', label: 'Purpose-built agents' },
  { value: '5', label: 'Practice areas covered' },
  { value: '100%', label: 'Outputs cited' },
  { value: 'AA', label: 'Accessibility (WCAG)' },
];

export default function LandingPage() {
  const { isAuthenticated } = useAuth();
  const ctaTo = isAuthenticated ? '/' : '/login';
  const ctaLabel = isAuthenticated ? 'Open Uniqus Hub' : 'Sign in';

  return (
    <div className="lp">
      {/* ── Top nav ─────────────────────────────────────────────────── */}
      <header className="lp-nav">
        <a href="#top" className="lp-nav-brand" aria-label="Uniqus Hub home">
          <span className="lp-nav-mark"><UniqusMark size={24} /></span>
          <span className="lp-nav-name">Uniqus<span className="lp-nav-name-light"> Hub</span></span>
        </a>
        <nav className="lp-nav-links" aria-label="Primary">
          <a href="#agents">Agents</a>
          <a href="#how">How it works</a>
          <a href="#proof">Why Uniqus</a>
        </nav>
        <div className="lp-nav-cta">
          <Link to="/login" className="lp-link">Sign in</Link>
          <a href="mailto:souravkumar@uniqus.com" className="lp-btn lp-btn-primary">
            Request access <span aria-hidden="true">→</span>
          </a>
        </div>
      </header>

      {/* ── Hero ────────────────────────────────────────────────────── */}
      <section id="top" className="lp-hero">
        <div className="lp-hero-bg" aria-hidden="true" />
        <div className="lp-hero-inner">
          <div className="lp-hero-eyebrow">ENTERPRISE AGENTS</div>
          <h1 className="lp-hero-title">
            Agent intelligence,<br />
            <em>ready to work.</em>
          </h1>
          <p className="lp-hero-sub">
            Sixteen purpose-built AI agents — investigation, classification,
            master data, vendor mapping, compliance — behind one workspace.
            Role-aware, audit-trailed, every output cited to its source.
          </p>
          <div className="lp-hero-cta">
            <Link to={ctaTo} className="lp-btn lp-btn-primary lp-btn-lg">
              {ctaLabel} <span aria-hidden="true">→</span>
            </Link>
            <a href="#agents" className="lp-btn lp-btn-link">
              See the agents
            </a>
          </div>
          <div className="lp-hero-foot">
            <span className="lp-status-dot" aria-hidden="true" />
            16 agents · 5 practice areas · audit-grade trails
          </div>
        </div>
      </section>

      {/* ── Featured agents ─────────────────────────────────────────── */}
      <section id="agents" className="lp-section">
        <div className="lp-section-head">
          <div className="lp-eyebrow">FEATURED AGENTS</div>
          <h2 className="lp-h2">
            Six agents already running in production.
          </h2>
          <p className="lp-section-sub">
            Each one trained on your taxonomy, your SOPs, your reference data.
            Every answer is cited. Every edit is yours to override. Ten more
            agents in the catalog — coming soon.
          </p>
        </div>
        <div className="lp-agents-grid">
          {FEATURED_AGENTS.map((a) => (
            <article key={a.name} className="lp-agent-card">
              <div className="lp-agent-mark"><UniqusMark size={32} /></div>
              <h3 className="lp-agent-name">{a.name}</h3>
              <div className="lp-agent-long">{a.long}</div>
              <p className="lp-agent-tagline">{a.tagline}</p>
              <div className="lp-agent-badge">{a.badge}</div>
            </article>
          ))}
        </div>
        <div className="lp-section-foot">
          <Link to={ctaTo} className="lp-btn lp-btn-link">
            See the full 16-agent catalog inside the hub
          </Link>
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────────── */}
      <section id="how" className="lp-section lp-section-alt">
        <div className="lp-section-head">
          <div className="lp-eyebrow">HOW IT WORKS</div>
          <h2 className="lp-h2">From sign-in to board-ready in four steps.</h2>
        </div>
        <ol className="lp-steps">
          {STEPS.map((s) => (
            <li key={s.n} className="lp-step">
              <div className="lp-step-n">{s.n}</div>
              <div className="lp-step-body">
                <h3 className="lp-step-title">{s.title}</h3>
                <p className="lp-step-text">{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      {/* ── Trust strip ─────────────────────────────────────────────── */}
      <section id="proof" className="lp-section">
        <div className="lp-section-head">
          <div className="lp-eyebrow">WHY UNIQUS</div>
          <h2 className="lp-h2">Built for finance, risk, and operations leaders.</h2>
          <p className="lp-section-sub">
            Uniqus Hub is the agent intelligence layer of Uniqus Consultech —
            the consulting firm trusted by 350+ clients across the US, India,
            and the Middle East. Every workflow you'd hand to a Uniqus
            specialist, you can hand to a Uniqus agent.
          </p>
        </div>
        <div className="lp-stats">
          {STATS.map((s) => (
            <div key={s.label} className="lp-stat">
              <div className="lp-stat-value">{s.value}</div>
              <div className="lp-stat-label">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Final CTA ───────────────────────────────────────────────── */}
      <section className="lp-cta-strip">
        <h2 className="lp-cta-title">Ready to put agents to work?</h2>
        <p className="lp-cta-sub">
          Sign in with your corporate email — your tenant, your data, your audit log.
        </p>
        <div className="lp-cta-actions">
          <Link to={ctaTo} className="lp-btn lp-btn-primary lp-btn-lg">
            {ctaLabel} <span aria-hidden="true">→</span>
          </Link>
          <a href="mailto:souravkumar@uniqus.com" className="lp-btn lp-btn-ghost">
            Request access
          </a>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────────── */}
      <footer className="lp-footer">
        <div className="lp-footer-row">
          <div className="lp-footer-brand">
            <span className="lp-footer-mark"><UniqusMark size={20} /></span>
            <div>
              <div className="lp-footer-name">Uniqus Hub</div>
              <div className="lp-footer-tag">Agent intelligence for the enterprise.</div>
            </div>
          </div>
          <nav className="lp-footer-links" aria-label="Footer">
            <a href="https://uniqus.com" target="_blank" rel="noreferrer">Uniqus Consultech</a>
            <a href="https://uniqus.com/privacy-policy" target="_blank" rel="noreferrer">Privacy</a>
            <a href="https://uniqus.com/terms-and-conditions" target="_blank" rel="noreferrer">Terms</a>
            <a href="mailto:souravkumar@uniqus.com">Contact</a>
          </nav>
          <div className="lp-footer-copy">
            © {new Date().getFullYear()} Uniqus Consultech
          </div>
        </div>
      </footer>
    </div>
  );
}
