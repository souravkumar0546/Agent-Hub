import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';

/**
 * Unified provider for toast notifications + confirm dialogs.
 *
 * Why combined: both need one top-level portal, both must survive route
 * transitions, and both call sites tend to live next to each other
 * (destructive action → confirm → toast on success/failure). Single import,
 * two hooks.
 *
 * Replaces native `window.alert()` / `window.confirm()` (H26 in the
 * April 2026 readiness review). Native dialogs blocked the event loop,
 * ignored theme tokens, and couldn't be embedded or styled.
 *
 * API:
 *   const toast = useToast();
 *   toast('Saved', { variant: 'success' });
 *   toast('Could not save', { variant: 'error', duration: 6000 });
 *
 *   const confirm = useConfirm();
 *   const ok = await confirm({
 *     title: 'Uninstall rca_investigation?',
 *     message: 'Members will lose access until you reinstall.',
 *     confirmLabel: 'Uninstall',
 *     destructive: true,
 *   });
 *   if (!ok) return;
 *
 * Both hooks must be called from inside `<DialogProvider>` (wired into
 * main.jsx). They throw if used outside the tree.
 */

const ToastContext = createContext(null);
const ConfirmContext = createContext(null);

let _nextToastId = 1;

export function DialogProvider({ children }) {
  // --- Toast state -------------------------------------------------------
  const [toasts, setToasts] = useState([]);

  const dismissToast = useCallback((id) => {
    setToasts((list) => list.filter((t) => t.id !== id));
  }, []);

  const toast = useCallback((message, opts = {}) => {
    const id = _nextToastId++;
    const variant = opts.variant || 'info';
    const duration = opts.duration ?? (variant === 'error' ? 6000 : 3500);
    setToasts((list) => [...list, { id, message, variant }]);
    if (duration > 0) {
      setTimeout(() => dismissToast(id), duration);
    }
    return id;
  }, [dismissToast]);

  // --- Confirm state -----------------------------------------------------
  // `pending` is either null (no dialog open) or
  // { title, message, confirmLabel, cancelLabel, destructive, resolve }.
  const [pending, setPending] = useState(null);
  const previouslyFocusedRef = useRef(null);

  const confirm = useCallback((opts) => new Promise((resolve) => {
    // Remember where focus was so we can return it on close.
    previouslyFocusedRef.current = typeof document !== 'undefined'
      ? document.activeElement
      : null;
    setPending({
      title: opts?.title ?? 'Are you sure?',
      message: opts?.message ?? '',
      confirmLabel: opts?.confirmLabel ?? 'Confirm',
      cancelLabel: opts?.cancelLabel ?? 'Cancel',
      destructive: !!opts?.destructive,
      resolve,
    });
  }), []);

  const closeConfirm = useCallback((result) => {
    setPending((p) => {
      if (p) p.resolve(result);
      return null;
    });
    // Restore focus after the modal unmounts.
    const prev = previouslyFocusedRef.current;
    previouslyFocusedRef.current = null;
    if (prev && typeof prev.focus === 'function') {
      // Defer so React has a chance to unmount the overlay first.
      setTimeout(() => prev.focus(), 0);
    }
  }, []);

  return (
    <ToastContext.Provider value={toast}>
      <ConfirmContext.Provider value={confirm}>
        {children}
        <ToastStack toasts={toasts} onDismiss={dismissToast} />
        {pending && (
          <ConfirmModal
            {...pending}
            onAccept={() => closeConfirm(true)}
            onCancel={() => closeConfirm(false)}
          />
        )}
      </ConfirmContext.Provider>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <DialogProvider>');
  return ctx;
}

export function useConfirm() {
  const ctx = useContext(ConfirmContext);
  if (!ctx) throw new Error('useConfirm must be used inside <DialogProvider>');
  return ctx;
}


// --- Internal components (not exported) ------------------------------------

function ToastStack({ toasts, onDismiss }) {
  if (toasts.length === 0) return null;
  return (
    <div
      aria-live="polite"
      aria-atomic="false"
      style={{
        position: 'fixed',
        bottom: 24,
        right: 24,
        zIndex: 80,
        display: 'flex',
        flexDirection: 'column-reverse',
        gap: 8,
        pointerEvents: 'none',
      }}
    >
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onDismiss={() => onDismiss(t.id)} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onDismiss }) {
  // Variant-specific accent colors — all use existing theme tokens so
  // dark/light flip just works.
  const variantStyle = {
    info:    { border: 'var(--border-strong)', accent: 'var(--ink-dim)' },
    success: { border: 'rgba(var(--accent-rgb), 0.45)', accent: 'var(--accent)' },
    warning: { border: 'rgba(var(--warn-rgb), 0.45)',   accent: 'var(--warn)' },
    error:   { border: 'rgba(var(--err-rgb), 0.45)',    accent: 'var(--err)' },
  }[toast.variant] || { border: 'var(--border-strong)', accent: 'var(--ink-dim)' };

  return (
    <div
      role={toast.variant === 'error' ? 'alert' : 'status'}
      className="toast"
      style={{
        position: 'static',
        bottom: 'auto',
        right: 'auto',
        borderColor: variantStyle.border,
        borderLeftWidth: 3,
        borderLeftStyle: 'solid',
        pointerEvents: 'auto',
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
      }}
    >
      <div style={{ flex: 1, minWidth: 0, color: 'var(--ink)' }}>
        {toast.message}
      </div>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss notification"
        style={{
          background: 'transparent',
          border: 0,
          color: variantStyle.accent,
          fontSize: 16,
          lineHeight: 1,
          padding: 2,
          cursor: 'pointer',
          flexShrink: 0,
        }}
      >
        ×
      </button>
    </div>
  );
}


function ConfirmModal({
  title,
  message,
  confirmLabel,
  cancelLabel,
  destructive,
  onAccept,
  onCancel,
}) {
  const acceptBtnRef = useRef(null);

  // Escape → cancel. Also return focus on mount to the destructive-primary
  // button so keyboard users can confirm with just Enter (or back out with
  // Tab-to-Cancel + Enter / Escape).
  useEffect(() => {
    function onKey(e) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onCancel();
      }
    }
    window.addEventListener('keydown', onKey);
    // Focus the primary button; without this, tab starts from body.
    // We put focus on Cancel for destructive variants so a reflex-Enter
    // doesn't delete something. Non-destructive focuses the primary.
    const focusTarget = destructive
      ? document.activeElement // keep current; user will Tab-select
      : acceptBtnRef.current;
    if (focusTarget && typeof focusTarget.focus === 'function') {
      focusTarget.focus();
    }
    return () => window.removeEventListener('keydown', onKey);
  }, [destructive, onCancel]);

  return (
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(e) => {
        // Click on overlay (not on the modal itself) cancels.
        if (e.target === e.currentTarget) onCancel();
      }}
    >
      <div
        className="modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby={message ? 'confirm-dialog-message' : undefined}
        style={{ width: 'min(460px, 100%)' }}
      >
        <div className="modal-head">
          <div style={{ minWidth: 0 }}>
            <div className="modal-title" id="confirm-dialog-title">{title}</div>
          </div>
          <button
            type="button"
            className="modal-close"
            onClick={onCancel}
            aria-label="Close"
          >
            ×
          </button>
        </div>
        {message && (
          <div
            className="modal-body"
            id="confirm-dialog-message"
            style={{ whiteSpace: 'pre-wrap', color: 'var(--ink-dim)', fontSize: 13, lineHeight: 1.55 }}
          >
            {message}
          </div>
        )}
        <div className="modal-actions">
          <button
            type="button"
            className="btn"
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            ref={acceptBtnRef}
            className={destructive ? 'btn btn-danger' : 'btn btn-primary'}
            onClick={onAccept}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
