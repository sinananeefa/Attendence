import React from 'react';
import { Inbox, AlertCircle, WifiOff, Search } from 'lucide-react';

type EmptyStateVariant = 'empty' | 'error' | 'offline' | 'search' | 'no-data';

interface EmptyStateProps {
  variant?: EmptyStateVariant;
  title?: string;
  message?: string;
  action?: React.ReactNode;
}

const iconMap: Record<EmptyStateVariant, React.ReactNode> = {
  empty:    <Inbox size={22} color="var(--text-dim)" />,
  'no-data':<Inbox size={22} color="var(--text-dim)" />,
  error:    <AlertCircle size={22} color="#fb7185" />,
  offline:  <WifiOff size={22} color="var(--text-dim)" />,
  search:   <Search size={22} color="var(--text-dim)" />,
};

export const EmptyState: React.FC<EmptyStateProps> = ({
  variant = 'empty',
  title = 'Nothing here yet',
  message = 'No records found.',
  action,
}) => (
  <div className="empty-state" role="status">
    <div className="empty-state__icon">{iconMap[variant]}</div>
    <p className="empty-state__title">{title}</p>
    <p className="empty-state__sub">{message}</p>
    {action && <div style={{ marginTop: '1rem' }}>{action}</div>}
  </div>
);

interface InlineErrorProps {
  message: string;
  onRetry?: () => void;
}

export const InlineError: React.FC<InlineErrorProps> = ({ message, onRetry }) => (
  <div className="alert alert--error" role="alert">
    <AlertCircle size={16} style={{ flexShrink: 0, marginTop: '1px' }} />
    <div style={{ flex: 1 }}>
      <span>{message}</span>
      {onRetry && (
        <button
          onClick={onRetry}
          style={{
            marginLeft: '0.75rem',
            background: 'none',
            border: 'none',
            color: '#fda4af',
            textDecoration: 'underline',
            cursor: 'pointer',
            fontSize: '0.85rem',
            fontWeight: 600,
          }}
        >
          Retry
        </button>
      )}
    </div>
  </div>
);
