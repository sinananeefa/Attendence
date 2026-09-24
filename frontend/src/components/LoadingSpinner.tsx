import React from 'react';

interface LoadingSpinnerProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  fullPage?: boolean;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  message = 'Loading…',
  size = 'md',
  fullPage = false,
}) => {
  const spinnerClass = size === 'sm' ? 'spinner spinner-sm' : size === 'lg' ? 'spinner spinner-lg' : 'spinner';

  if (fullPage) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '60vh',
          gap: '1rem',
        }}
        role="status"
        aria-live="polite"
      >
        <div className={spinnerClass} />
        <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>{message}</span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: '0.65rem',
        padding: '2.5rem',
        justifyContent: 'center',
        color: 'var(--text-muted)',
        fontSize: '0.875rem',
      }}
      role="status"
      aria-live="polite"
    >
      <div className={spinnerClass} />
      <span>{message}</span>
    </div>
  );
};

interface PageLoadingProps {
  message?: string;
}

export const PageLoading: React.FC<PageLoadingProps> = ({ message = 'Loading dashboard…' }) => (
  <LoadingSpinner message={message} size="lg" fullPage />
);

interface InlineLoadingProps {
  text?: string;
}

export const InlineLoading: React.FC<InlineLoadingProps> = ({ text = 'Processing…' }) => (
  <span
    style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.4rem',
      color: 'var(--text-muted)',
      fontSize: '0.82rem',
    }}
    role="status"
  >
    <span className="spinner spinner-sm" />
    {text}
  </span>
);
