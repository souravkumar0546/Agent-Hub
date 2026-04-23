import { useEffect, useRef, useState } from 'react';

/**
 * Inline-editable field. Click → textarea with current value.
 * Commit on blur / Enter (single-line) / ⌘-Enter (multiline). Esc cancels.
 * Color-coded by `status`: filled / partial / empty.
 *
 * `paper=true` opts into the white-paper styling used inside TemplatePreview.
 * Default styling targets the dark UI shell.
 */
export default function EditableField({
  value = '',
  placeholder = '',
  status = 'empty',
  multiline = true,
  busy = false,
  paper = false,
  onSave,
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const ref = useRef(null);

  useEffect(() => { setDraft(value); }, [value]);

  useEffect(() => {
    if (editing && ref.current) {
      ref.current.focus();
      ref.current.style.height = 'auto';
      ref.current.style.height = ref.current.scrollHeight + 'px';
      const len = ref.current.value.length;
      ref.current.setSelectionRange(len, len);
    }
  }, [editing]);

  function commit() {
    setEditing(false);
    const trimmed = (draft ?? '').replace(/\r/g, '');
    if (trimmed !== value && onSave) onSave(trimmed);
  }

  function cancel() {
    setDraft(value);
    setEditing(false);
  }

  function onKeyDown(e) {
    if (e.key === 'Escape') { e.preventDefault(); cancel(); }
    if (!multiline && e.key === 'Enter') { e.preventDefault(); commit(); }
    if (multiline && (e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); commit(); }
  }

  const hasContent = Boolean(value && value.trim());
  const klass = [
    'ef',
    paper && 'ef--paper',
    editing && 'ef--editing',
    !hasContent && 'ef--empty',
    `ef--${status}`,
  ].filter(Boolean).join(' ');

  if (editing) {
    return (
      <textarea
        ref={ref}
        className={klass}
        value={draft ?? ''}
        onChange={(e) => {
          setDraft(e.target.value);
          e.target.style.height = 'auto';
          e.target.style.height = e.target.scrollHeight + 'px';
        }}
        onBlur={commit}
        onKeyDown={onKeyDown}
        rows={multiline ? 3 : 1}
        disabled={busy}
      />
    );
  }

  return (
    <div
      className={klass}
      onClick={() => !busy && setEditing(true)}
      title={busy ? 'Run in progress…' : 'Click to edit'}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => { if (e.key === 'Enter') setEditing(true); }}
    >
      {hasContent ? value : <span className="ef-placeholder">{placeholder || '—'}</span>}
    </div>
  );
}
