/**
 * Two tiny loading primitives, both zero-dep.
 *
 * <Spinner>       — inline SVG circle that spins. Sized via `size` prop.
 * <LoadingBlock>  — full-width "Loading…" placeholder used where a page
 *                   region is waiting on its initial fetch. Matches the
 *                   existing `.empty` dashed-border look so transitions
 *                   don't jank.
 *
 * Placed here so every page fetches from one consistent source (M39 in
 * the readiness review).
 */


/** Inline spinning circle. Use inside a button (`<button><Spinner size={12}/> Saving…</button>`)
 *  or next to inline text. Inherits `currentColor` for its stroke. */
export function Spinner({ size = 14, label = 'Loading' }) {
  const s = Number(size) || 14;
  return (
    <svg
      role="status"
      aria-label={label}
      width={s}
      height={s}
      viewBox="0 0 24 24"
      fill="none"
      style={{
        display: 'inline-block',
        verticalAlign: 'text-bottom',
        animation: 'sah-spin 0.9s linear infinite',
      }}
    >
      <circle
        cx="12"
        cy="12"
        r="9"
        stroke="currentColor"
        strokeOpacity="0.2"
        strokeWidth="3"
      />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}


/** Full-width loading placeholder — drop-in replacement for the page-level
 *  "Loading…" divs that used to be either missing or bare text. */
export function LoadingBlock({ text = 'Loading\u2026', compact = false }) {
  return (
    <div
      className="empty"
      role="status"
      aria-live="polite"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 10,
        padding: compact ? '24px 16px' : undefined,
        color: 'var(--ink-dim)',
      }}
    >
      <span style={{ color: 'var(--ink-muted)' }}>
        <Spinner size={16} label={text} />
      </span>
      <span>{text}</span>
    </div>
  );
}
