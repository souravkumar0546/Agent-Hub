/** Slim site-wide footer.
 *
 * Two columns: brand mark + product line on the left, "© Uniqus Consultech"
 * on the right. Stays minimal — no Privacy / Terms links until those
 * pages actually exist (broken anchors are worse than no anchors).
 *
 * Pushed to the bottom of the viewport via flex layout in `.scroll-region`,
 * so on short pages it sits at the bottom rather than mid-page.
 */
export default function Footer() {
  const year = new Date().getFullYear();
  return (
    <footer className="site-footer">
      <div className="site-footer-row">
        <div className="site-footer-brand">
          <span className="site-footer-mark">Uniqus Labs</span>
          <span className="site-footer-divider" aria-hidden="true">·</span>
          <span className="site-footer-tag">AI agents for enterprise teams.</span>
        </div>
        <div className="site-footer-meta">
          © {year} Uniqus Consultech
        </div>
      </div>
    </footer>
  );
}
