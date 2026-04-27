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
    tagline: 'Drafts a full RCA report in about an hour. Every line is linked back to the SOP it came from. Export to Word when you’re done.',
    badge: '~1 hr per report',
  },
  {
    name: 'Curator',
    long: 'Data Classifier',
    tagline: 'Sort thousands of new records into your taxonomy. You can review and override every classification before it ships.',
    badge: '1,000s of rows / hr',
  },
  {
    name: 'Forge',
    long: 'Master Builder',
    tagline: 'Turns messy classifications into a clean master dataset. Every change is logged. Reviewers can fix anything inline.',
    badge: 'reviewable inline',
  },
  {
    name: 'Echo',
    long: 'Data Enrichment',
    tagline: 'Adds the attributes you’re missing from outside sources. The original value is kept, so you can see what came from where.',
    badge: 'sources kept',
  },
  {
    name: 'Twin',
    long: 'Group Duplicates',
    tagline: 'Finds duplicates and near-duplicates across columns. Catches the awkward variants regex misses.',
    badge: 'catches variants',
  },
  {
    name: 'Sonar',
    long: 'Lookup Agent',
    tagline: 'Scores how close two records are, column by column. Gives you one weighted verdict per row.',
    badge: 'one verdict per row',
  },
];

const STEPS = [
  {
    n: '01',
    title: 'Sign in with your work email',
    body: 'Type your email. We figure out which company you belong to before you type a password.',
  },
  {
    n: '02',
    title: 'Add the agents you need',
    body: 'There are 16 in the library. You probably only need three or four. Add those.',
  },
  {
    n: '03',
    title: 'Run an agent',
    body: 'Upload your file or describe what you need. The agent works through it. You can edit anything it gets wrong, and it won’t change your edits later.',
  },
  {
    n: '04',
    title: 'Export or share',
    body: 'Download a Word doc, share the link with your team, or come back tomorrow. Your work is saved.',
  },
];

const STATS = [
  { value: '6', label: 'Agents live today' },
  { value: '16', label: 'Total in the catalog' },
  { value: '5', label: 'Practice areas' },
  { value: 'Cited', label: 'Every answer' },
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
          <div className="lp-hero-eyebrow">UNIQUS HUB</div>
          <h1 className="lp-hero-title">
            AI agents that<br />
            <em>do the work.</em>
          </h1>
          <p className="lp-hero-sub">
            Run investigations, classify your data, build clean master records,
            find duplicates. Six agents are live today, ten more are on the way.
            Each one works from your files and shows you exactly where every
            answer came from.
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
            Built by Uniqus Consultech
          </div>
        </div>
      </section>

      {/* ── Featured agents ─────────────────────────────────────────── */}
      <section id="agents" className="lp-section">
        <div className="lp-section-head">
          <div className="lp-eyebrow">WHAT&rsquo;S LIVE TODAY</div>
          <h2 className="lp-h2">Six agents you can use right now.</h2>
          <p className="lp-section-sub">
            They work from your files. Every answer points back to its source.
            You can edit anything the AI gets wrong, and the agent won&rsquo;t
            quietly change your edits later.
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
            See the full catalog inside
          </Link>
        </div>
      </section>

      {/* ── How it works ────────────────────────────────────────────── */}
      <section id="how" className="lp-section lp-section-alt">
        <div className="lp-section-head">
          <div className="lp-eyebrow">HOW IT WORKS</div>
          <h2 className="lp-h2">Four steps to your first run.</h2>
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
          <h2 className="lp-h2">For finance, risk, and operations teams.</h2>
          <p className="lp-section-sub">
            We&rsquo;re a part of Uniqus Consultech, a consulting firm working
            with 350+ enterprises across the US, India, and the Middle East.
            The agents handle the work that used to need a specialist.
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
        <h2 className="lp-cta-title">Ready to try it?</h2>
        <p className="lp-cta-sub">
          Sign in with your work email. Takes about 30 seconds.
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
              <div className="lp-footer-tag">AI agents for enterprise teams.</div>
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
