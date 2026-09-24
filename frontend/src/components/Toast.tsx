import React, { createContext, useCallback, useContext, useRef, useState } from 'react';
import { CheckCircle2, XCircle, AlertTriangle, Info, X } from 'lucide-react';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

interface Toast {
  id: string;
  type: ToastType;
  title: string;
  message?: string;
  exiting?: boolean;
}

interface ToastContextValue {
  toast: (type: ToastType, title: string, message?: string) => void;
  success: (title: string, message?: string) => void;
  error: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

const ICONS: Record<ToastType, React.ReactNode> = {
  success: <CheckCircle2 size={18} color="#34d399" />,
  error:   <XCircle size={18} color="#fb7185" />,
  warning: <AlertTriangle size={18} color="#fbbf24" />,
  info:    <Info size={18} color="#60a5fa" />,
};

const AUTO_DISMISS = 4000; // ms

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const timers = useRef<Map<string, ReturnType<typeof setTimeout>>>(new Map());

  const remove = useCallback((id: string) => {
    // animate out then remove
    setToasts((t) => t.map((x) => (x.id === id ? { ...x, exiting: true } : x)));
    setTimeout(() => {
      setToasts((t) => t.filter((x) => x.id !== id));
    }, 260);
    const timer = timers.current.get(id);
    if (timer) { clearTimeout(timer); timers.current.delete(id); }
  }, []);

  const toast = useCallback((type: ToastType, title: string, message?: string) => {
    const id = `${Date.now()}-${Math.random()}`;
    setToasts((t) => [...t, { id, type, title, message }]);
    const timer = setTimeout(() => remove(id), AUTO_DISMISS);
    timers.current.set(id, timer);
  }, [remove]);

  const contextValue: ToastContextValue = {
    toast,
    success: (t, m) => toast('success', t, m),
    error:   (t, m) => toast('error', t, m),
    warning: (t, m) => toast('warning', t, m),
    info:    (t, m) => toast('info', t, m),
  };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      <div className="toast-container" role="region" aria-label="Notifications">
        {toasts.map((t) => (
          <div key={t.id} className={`toast toast--${t.type}${t.exiting ? ' exiting' : ''}`} role={t.type === 'error' ? 'alert' : 'status'} aria-live={t.type === 'error' ? 'assertive' : 'polite'}>
            <span className="toast__icon" aria-hidden="true">{ICONS[t.type]}</span>
            <div className="toast__content">
              <div className="toast__title">{t.title}</div>
              {t.message && <div className="toast__message">{t.message}</div>}
            </div>
            <button
              className="toast__close"
              onClick={() => remove(t.id)}
              aria-label="Dismiss notification"
            >×</button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
};

export const useToast = (): ToastContextValue => {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within <ToastProvider>');
  return ctx;
};
