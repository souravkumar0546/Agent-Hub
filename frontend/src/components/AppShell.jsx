import { useCallback, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import AssistantWidget from './AssistantWidget.jsx';
import Footer from './Footer.jsx';
import Sidebar from './Sidebar.jsx';
import TopBar from './TopBar.jsx';

export default function AppShell({ crumbs, children }) {
  // Mobile nav drawer state. On desktop (>=769px) the sidebar is always
  // visible via CSS and this flag has no effect. On mobile the sidebar
  // starts hidden and slides in when `navOpen` flips true.
  const [navOpen, setNavOpen] = useState(false);
  const location = useLocation();

  const closeNav = useCallback(() => setNavOpen(false), []);
  const toggleNav = useCallback(() => setNavOpen((v) => !v), []);

  // Auto-close on route change — stops the drawer from lingering after the
  // user taps a link. Desktop users never see this happen because the
  // drawer styling doesn't apply above 768px.
  useEffect(() => { closeNav(); }, [location.pathname, closeNav]);

  // Also close on Escape for keyboard users.
  useEffect(() => {
    if (!navOpen) return undefined;
    function onKey(e) { if (e.key === 'Escape') closeNav(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [navOpen, closeNav]);

  return (
    <div className={`app-shell${navOpen ? ' nav-open' : ''}`}>
      <Sidebar />
      {/* Dimmed overlay behind the drawer on mobile — click anywhere to close.
          Pure CSS could do this with :target, but we need the React state
          anyway for the hamburger button, so reuse it. */}
      {navOpen && (
        <div
          className="app-shell-nav-overlay"
          onClick={closeNav}
          aria-hidden="true"
        />
      )}
      <div className="main">
        <TopBar crumbs={crumbs} onToggleNav={toggleNav} navOpen={navOpen} />
        <div className="scroll-region">
          {children}
          <Footer />
        </div>
      </div>
      {/* Floating platform assistant — rendered on every authenticated page,
          hidden automatically on the login page because that never renders
          AppShell. */}
      <AssistantWidget />
    </div>
  );
}
