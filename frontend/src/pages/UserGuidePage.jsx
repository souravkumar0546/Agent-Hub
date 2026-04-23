import { useEffect, useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import AppShell from '../components/AppShell.jsx';
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

const SECTIONS = [
  { id: 'getting-started', title: 'Getting started', body: gettingStarted },
  { id: 'investigation', title: 'Investigation (RCA)', body: investigation },
  { id: 'data-classifier', title: 'Data Classifier', body: classifier },
  { id: 'master-builder', title: 'Master Builder', body: masterBuilder },
  { id: 'data-enrichment', title: 'Data Enrichment', body: enrichment },
  { id: 'duplicate-groups', title: 'Duplicate Groups', body: duplicates },
  { id: 'lookup', title: 'Lookup Agent', body: lookup },
  { id: 'integrations', title: 'Integrations', body: integrations },
  { id: 'faq', title: 'FAQ', body: faq },
];

/** Observe which section is closest to the top of the scroll area. */
function useActiveSection() {
  const [active, setActive] = useState(SECTIONS[0].id);

  useEffect(() => {
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
    for (const s of SECTIONS) {
      const el = document.getElementById(s.id);
      if (el) observer.observe(el);
    }
    return () => observer.disconnect();
  }, []);

  return active;
}

export default function UserGuidePage() {
  const active = useActiveSection();
  const { productName } = useBrand();
  const components = useMemo(() => ({
    // Use the platform's table style for any `| - |` blocks in the markdown.
    table: (props) => <table className="table" {...props} />,
  }), []);

  return (
    <AppShell crumbs={['User Guide']}>
      <div className="guide-layout">
        <article className="guide-content">
          <header className="guide-hero">
            <h1 className="page-title">User <em>guide</em></h1>
            <p className="page-subtitle">
              How to use {productName} — agents, integrations, admin tools, and the small details that save time.
            </p>
          </header>

          {SECTIONS.map((s) => (
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
            {SECTIONS.map((s) => (
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
