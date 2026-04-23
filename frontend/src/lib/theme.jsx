import { createContext, useCallback, useContext, useEffect, useState } from 'react';

/**
 * Theme provider — flips `<html data-theme="...">` between 'dark' and 'light'.
 * `tokens.css` defines both palettes keyed off the attribute, so the swap is
 * pure CSS. The user's choice persists in localStorage across reloads.
 *
 * Default = 'light'. We intentionally don't auto-follow `prefers-color-scheme`
 * — light is the Uniqus brand look, and we only switch when the user asks
 * for dark in Settings.
 */

const STORAGE_KEY = 'sah.theme';
const ThemeContext = createContext(null);

function readStoredTheme() {
  if (typeof localStorage === 'undefined') return 'light';
  const v = localStorage.getItem(STORAGE_KEY);
  return v === 'light' || v === 'dark' ? v : 'light';
}

function applyTheme(theme) {
  if (typeof document === 'undefined') return;
  document.documentElement.setAttribute('data-theme', theme);
}

export function ThemeProvider({ children }) {
  const [theme, setThemeState] = useState(readStoredTheme);

  // Apply immediately on mount so there's no dark-to-light flash for users
  // whose stored preference is light.
  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const setTheme = useCallback((next) => {
    if (next !== 'light' && next !== 'dark') return;
    setThemeState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch (_) { /* quota / private mode */ }
  }, []);

  const toggleTheme = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  }, [theme, setTheme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, toggleTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useTheme must be used inside ThemeProvider');
  return ctx;
}
