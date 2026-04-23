import React from 'react';
import ReactDOM from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App.jsx';
import { DialogProvider } from './components/Dialog.jsx';
import ErrorBoundary from './components/ErrorBoundary.jsx';
import { AuthProvider } from './lib/auth.jsx';
import { ThemeProvider } from './lib/theme.jsx';
import './theme/tokens.css';
import './theme/app.css';

// Apply the stored theme synchronously (before React mounts) so there's no
// flash of the wrong palette. Default is light — users who explicitly chose
// dark in Settings have that recorded in localStorage and get dark; everyone
// else lands on light. Mirrors ThemeProvider so the two sources can't disagree.
(function applyStoredTheme() {
  try {
    const t = localStorage.getItem('sah.theme');
    document.documentElement.setAttribute('data-theme', t === 'dark' ? 'dark' : 'light');
  } catch (_) {
    document.documentElement.setAttribute('data-theme', 'light');
  }
})();

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          {/* ErrorBoundary sits outside <Routes> (which live inside App) so a
              route render crash still surfaces the themed fallback instead of
              unmounting the entire tree. Kept inside the providers so the
              fallback inherits theme tokens and the auth context (future
              enhancement: let the fallback copy includes "signed in as X"). */}
          <ErrorBoundary>
            <DialogProvider>
              <App />
            </DialogProvider>
          </ErrorBoundary>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>,
);
