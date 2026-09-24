import React, { useEffect, useId, useRef } from 'react';
import { AlertTriangle } from 'lucide-react';

interface ConfirmDialogProps {
  isOpen: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
  onCancel: () => void;
  isLoading?: boolean;
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'warning',
  onConfirm,
  onCancel,
  isLoading = false,
}) => {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogId = useId();

  useEffect(() => {
    if (!isOpen) return;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    cancelRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !isLoading) onCancel();
      if (event.key === 'Tab') {
        const dialog = document.getElementById(dialogId);
        const focusable = dialog?.querySelectorAll<HTMLElement>('button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])');
        if (!focusable?.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      previouslyFocused?.focus();
    };
  }, [isOpen, isLoading, onCancel, dialogId]);

  if (!isOpen) return null;

  const colorMap = {
    danger:  { icon: '#fb7185', btn: 'btn btn-danger', border: 'rgba(244,63,94,0.35)' },
    warning: { icon: '#fbbf24', btn: 'btn btn-danger', border: 'rgba(245,158,11,0.35)' },
    info:    { icon: '#60a5fa', btn: 'btn btn-primary', border: 'rgba(59,130,246,0.35)' },
  };
  const colors = colorMap[variant];

  return (
    <div
      className="modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      aria-describedby={`${dialogId}-description`}
      onClick={(e) => { if (e.target === e.currentTarget) onCancel(); }}
    >
      <div className="modal-panel" id={dialogId}>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
          <div
            style={{
              width: '42px', height: '42px', borderRadius: '10px', flexShrink: 0,
              background: `rgba(245,158,11,0.1)`,
              border: `1px solid ${colors.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >
            <AlertTriangle size={20} color={colors.icon} />
          </div>
          <div>
            <h3 id="confirm-title" style={{ fontSize: '1rem', fontWeight: 700, color: 'var(--text-main)', marginBottom: '0.35rem' }}>
              {title}
            </h3>
            <p id={`${dialogId}-description`} style={{ color: 'var(--text-muted)', fontSize: '0.875rem', lineHeight: 1.55 }}>
              {message}
            </p>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem', justifyContent: 'flex-end' }}>
          <button ref={cancelRef} className="btn btn-secondary" onClick={onCancel} disabled={isLoading}>
            {cancelLabel}
          </button>
          <button className={colors.btn} onClick={onConfirm} disabled={isLoading} aria-busy={isLoading}>
            {isLoading ? (
              <>
                <span className="spinner spinner-sm" />
                Processing…
              </>
            ) : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
};
