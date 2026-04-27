import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import AppShell from '../components/AppShell.jsx';
import { useAuth } from '../lib/auth.jsx';
import { useBrand } from '../lib/brand.js';

// One section per file. Loaded as raw strings via Vite's `?raw` import —
// editing any of these files ships a documentation update with the next build,
// no code changes required.
import gettingStarted from '../content/user-guide/01-getting-started.md?raw';
import investigation from '../content/user-guide/02-investigation.md?raw';
import classifier from '../content/user-guide/03-data-classifier.md?raw';
import masterBuilder from '../content/user-guide/04-master-builder.md?raw';
import enrichment from '../content/user-guide/05-data-enrichment.md?raw';
import duplicates from '../content/user-guide/06-duplicate-groups.md?raw';
import lookup from '../content/user-guide/07-lookup.md?raw';
import integrations from '../content/user-guide/08-integrations.md?raw';
import faq from '../content/user-guide/09-faq.md?raw';
import membersAdmin from '../content/user-guide/10-members-admin.md?raw';
import platformAdmin from '../content/user-guide/11-platform-admin.md?raw';

// Each section declares which roles it's relevant to. Members shouldn't
// see admin-only chapters (Integrations setup, Members management, Platform
// administration); admins see everything; super admins additionally see the
// Platform chapter. Filtering happens once at render and the side-rail TOC
// reflects the filtered list so users never see a link to content that
// isn't actually on the page.
const ROLE_MEMBER = 'MEMBER';
const ROLE_ORG_ADMIN = 'ORG_ADMIN';
const ROLE_SUPER_ADMIN = 'SUPER_ADMIN';
const ALL_ROLES = [ROLE_MEMBER, ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN];

const SECTIONS = [
  { id: 'getting-started', title: 'Getting started', body: gettingStarted, roles: ALL_ROLES },
  { id: 'investigation', title: 'Investigation (RCA)', body: investigation, roles: ALL_ROLES },
  { id: 'data-classifier', title: 'Data Classifier', body: classifier, roles: ALL_ROLES },
  { id: 'master-builder', title: 'Master Builder', body: masterBuilder, roles: ALL_ROLES },
  { id: 'data-enrichment', title: 'Data Enrichment', body: enrichment, roles: ALL_ROLES },
  { id: 'duplicate-groups', title: 'Duplicate Groups', body: duplicates, roles: ALL_ROLES },
  { id: 'lookup', title: 'Lookup Agent', body: lookup, roles: ALL_ROLES },
  // Admin-only: integrations setup needs credentials; members can use the
  // results but shouldn't see the connection guide.
  { id: 'integrations', title: 'Integrations', body: integrations, roles: [ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN] },
  { id: 'members-admin', title: 'Managing members', body: membersAdmin, roles: [ROLE_ORG_ADMIN, ROLE_SUPER_ADMIN] },
  { id: 'platform-admin', title: 'Platform administration', body: platformAdmin, roles: [ROLE_SUPER_ADMIN] },
  { id: 'faq', title: 'FAQ', body: faq, roles: ALL_ROLES },
];

function roleFor({ isSuperAdmin, isOrgAdmin }) {
  if (isSuperAdmin) return ROLE_SUPER_ADMIN;
  if (isOrgAdmin) return ROLE_ORG_ADMIN;
  return ROLE_MEMBER;
}

/** Observe which section is closest to the top of the scroll area. */
function useActiveSection(sections) {
  const [active, setActive] = useState(sections[0]?.id);

  useEffect(() => {
    if (!sections.length) return undefined;
    setActive((prev) => (sections.some((s) => s.id === prev) ? prev : sections[0].id));
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
        if (visible.length) setActive(visible[0].target.id);
      },
      {
        // Counting the top 40 % of the viewport as "above the fold" — avoids
        // the TOC highlight flapping when two sections are both in view.
        rootMargin: '-10% 0px -60% 0px',
        threshold: 0,
      },
    );
    for (const s of sections) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, [sections]);

  return active;
}

export default function UserGuidePage() {
  const { isSuperAdmin, isOrgAdmin } = useAuth();
  const role = roleFor({ isSuperAdmin, isOrgAdmin });
  const sections = useMemo(() => SECTIONS.filter((s) => s.roles.includes(role)), [role]);
  const active = useActiveSection(sections);
  const { productName } = useBrand();
  const components = useMemo(() => ({
    // Use the platform's table style for any `| - |` blocks in the markdown.
    table: (props) => <table className="table" {...props} />,
  }), []);

  const subtitle = role === ROLE_SUPER_ADMIN
    ? `How to run ${productName} as platform admin — onboard tenants, manage the agent catalog, and run the day-to-day.`
    : role === ROLE_ORG_ADMIN
      ? `How to run ${productName} for your team — agents, members, integrations, audit, and the small details that save time.`
      : `How to use ${productName} — your agents, runs, and reports.`;

  return (
    <AppShell crumbs={['User Guide']}>
      <div className="guide-layout">
        <article className="guide-content">
          <header className="guide-hero">
            <h1 className="page-title">User <em>guide</em></h1>
            <p className="page-subtitle">{subtitle}</p>
          </header>

          {sections.map((s) => (
            <section key={s.id} id={s.id} className="guide-section">
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
                {s.body}
              </ReactMarkdown>
            </section>
          ))}
        </article>

        <nav className="guide-toc">
          <div className="guide-toc-label">On this page</div>
          <ul>
            {sections.map((s) => (
              <li key={s.id} className={active === s.id ? 'active' : ''}>
                <a href={`#${s.id}`}>{s.title}</a>
              </li>
            ))}
          </ul>
        </nav>
      </div>
    </AppShell>
  );
}
