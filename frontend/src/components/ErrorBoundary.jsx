import React from 'react';

/**
 * Top-level React error boundary.
 *
 * Why this exists: before this boundary landed, a single uncaught render
 * exception anywhere in the tree unmounted the whole app and left users
 * staring at a blank white page (see C18 / C5 in the April 2026
 * production-readiness review). This gives us a themed fallback, a way for
 * users to recover without closing the tab, and — critically — a single
 * chokepoint where Sentry / OpenTelemetry capture will plug in once
 * observability is wired. `componentDidCatch` is the only place React
 * exposes the raw `Error` + component stack to us.
 *
 * Placement: wraps `<App />` in `main.jsx`, i.e. outside `<Routes>` so a
 * route-level render crash still renders the fallback instead of propagating
 * all the way to React's default unmount-on-error behaviour.
 *
 * Caveats:
 * - Only catches errors thrown during render / lifecycle / constructor in
 *   components *below* it. Event handlers, setTimeout callbacks, promise
 *   rejections, and errors inside `useEffect` cleanup don't reach it — that's
 *   a React-documented limitation. Those need `window.addEventListener('error')`
 *   / `'unhandledrejection'` listeners which we can add separately.
 * - "Try again" just resets the boundary's state. If the underlying bug is
 *   deterministic the next render will throw again; if it was transient
 *   (a flaky network race, a missing-auth edge case) the retry will stick.
 */
export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
    this.handleReset = this.handleReset.bind(this);
    this.handleReload = this.handleReload.bind(this);
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    // Dev-time visibility. Devtools will also surface the error overlay.
    // TODO(observability): when Sentry is wired, send `error` + `info.componentStack`
    // here with user/org breadcrumbs (see phase-1 item in the readiness review).
    // eslint-disable-next-line no-console
    console.error('ErrorBoundary caught a render error:', error, info);
  }

  handleReset() {
    this.setState({ hasError: false, error: null });
  }

  handleReload() {
    // Full reload, bypasses the React state machine entirely. Last-ditch
    // recovery — keeps the tab but tosses any in-memory state that might
    // itself be the source of the crash.
    window.location.reload();
  }

  render() {
    if (!this.state.hasError) {
      return this.props.children;
    }

    return (
      <div
        role="alert"
        aria-live="assertive"
        style={{
          minHeight: '100vh',
          display: 'grid',
          placeItems: 'center',
          padding: 24,
          background: 'var(--bg)',
          color: 'var(--ink)',
          fontFamily: 'var(--sans)',
        }}
      >
        <div
          style={{
            width: '100%',
            maxWidth: 520,
            background: 'var(--bg-card)',
            border: '1px solid var(--border)',
            borderRadius: 'var(--radius-lg)',
            padding: '28px 28px 24px',
            textAlign: 'center',
          }}
        >
          <h1
            style={{
              fontFamily: 'var(--sans)',
              fontStyle: 'normal',
              fontSize: 28,
              fontWeight: 800,
              letterSpacing: '-0.025em',
              marginBottom: 8,
              color: 'var(--ink)',
            }}
          >
            Something went wrong
          </h1>
          <p
            style={{
              color: 'var(--ink-dim)',
              fontSize: 14,
              lineHeight: 1.55,
              marginBottom: 22,
            }}
          >
            The error was logged. Try reloading, and let the team know if it
            keeps happening.
          </p>

          <div
            style={{
              display: 'flex',
              gap: 10,
              justifyContent: 'center',
              flexWrap: 'wrap',
            }}
          >
            <button
              type="button"
              className="btn"
              onClick={this.handleReset}
            >
              Try again
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={this.handleReload}
            >
              Reload
            </button>
          </div>
        </div>
      </div>
    );
  }
}
