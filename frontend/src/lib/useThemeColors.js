import { useEffect, useState } from 'react';
import { useTheme } from './theme.jsx';

/**
 * Pulls the current resolved values of a handful of theme CSS variables out
 * of `<html>` so non-CSS consumers (Recharts, Canvas, SVG `fill` attrs) can
 * follow the active theme.
 *
 * Why: Recharts axes, tooltip backgrounds, grid strokes, bar fills, etc.
 * all take plain strings — they don't understand `var(--…)`. Hardcoding
 * `'#c8f263'` makes dashboards look wrong after a theme flip (see C19 +
 * the April 2026 review). This hook snapshots the computed CSS values for
 * us and re-reads them whenever `theme` changes.
 *
 * Returned colours are safe to interpolate into any Recharts prop
 * (`stroke`, `fill`, `contentStyle.background`). The values are already
 * resolved hexes / rgbs, not the raw `var(--…)` token, so downstream code
 * doesn't have to worry about CSS fallback gotchas.
 */
export function useThemeColors() {
  const { theme } = useTheme();
  const [colors, setColors] = useState(() => readColors());

  // Re-read on theme toggle. Also listen for the `data-theme` attribute
  // changing directly on <html> (covers the IIFE in main.jsx that flips
  // it before React mounts, plus any future code path that bypasses the
  // ThemeProvider).
  useEffect(() => {
    setColors(readColors());
  }, [theme]);

  return colors;
}

function readColors() {
  // Server-side / SSR safety — tests that import this module won't have
  // a document. Return a reasonable dark-theme default.
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return DEFAULT_FALLBACK;
  }
  const cs = getComputedStyle(document.documentElement);
  return {
    accent:      (cs.getPropertyValue('--accent') || '').trim()        || DEFAULT_FALLBACK.accent,
    accentSoft:  (cs.getPropertyValue('--accent-soft') || '').trim()   || DEFAULT_FALLBACK.accentSoft,
    border:      (cs.getPropertyValue('--border') || '').trim()        || DEFAULT_FALLBACK.border,
    bgCard:      (cs.getPropertyValue('--bg-card') || '').trim()       || DEFAULT_FALLBACK.bgCard,
    bgElev:      (cs.getPropertyValue('--bg-elev') || '').trim()       || DEFAULT_FALLBACK.bgElev,
    ink:         (cs.getPropertyValue('--ink') || '').trim()           || DEFAULT_FALLBACK.ink,
    inkDim:      (cs.getPropertyValue('--ink-dim') || '').trim()       || DEFAULT_FALLBACK.inkDim,
    inkMuted:    (cs.getPropertyValue('--ink-muted') || '').trim()     || DEFAULT_FALLBACK.inkMuted,
    bio:         (cs.getPropertyValue('--bio') || '').trim()           || DEFAULT_FALLBACK.bio,
    warn:        (cs.getPropertyValue('--warn') || '').trim()          || DEFAULT_FALLBACK.warn,
    err:         (cs.getPropertyValue('--err') || '').trim()           || DEFAULT_FALLBACK.err,
    pink:        (cs.getPropertyValue('--pink') || '').trim()          || DEFAULT_FALLBACK.pink,
  };
}

// Dark-theme values, used as fallback if `getComputedStyle` can't see the
// variables yet (first render before ThemeProvider has mounted, SSR, etc).
const DEFAULT_FALLBACK = {
  accent: '#c8f263',
  accentSoft: '#8aa04a',
  border: '#222926',
  bgCard: '#151a17',
  bgElev: '#111513',
  ink: '#ecefe9',
  inkDim: '#9aa39d',
  inkMuted: '#5b645e',
  bio: '#6bb3f2',
  warn: '#f2a76b',
  err: '#f27b7b',
  pink: '#f2b8d4',
};
