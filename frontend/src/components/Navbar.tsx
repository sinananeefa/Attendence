import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Role } from '../types';
import { LogOut, User as UserIcon, ShieldCheck, Menu, X } from 'lucide-react';

const ROLE_COLORS: Record<string, { bg: string; color: string; border: string }> = {
  ADMIN:   { bg: 'rgba(59,130,246,0.15)',  color: '#93c5fd', border: 'rgba(59,130,246,0.3)'  },
  HOD:     { bg: 'rgba(245,158,11,0.15)',  color: '#fde68a', border: 'rgba(245,158,11,0.3)'  },
  FACULTY: { bg: 'rgba(16,185,129,0.15)',  color: '#6ee7b7', border: 'rgba(16,185,129,0.3)'  },
  MENTOR:  { bg: 'rgba(6,182,212,0.15)',   color: '#67e8f9', border: 'rgba(6,182,212,0.3)'   },
  STUDENT: { bg: 'rgba(34,211,238,0.15)',  color: '#a5f3fc', border: 'rgba(34,211,238,0.3)'  },
};

export const Navbar: React.FC = () => {
  const { user, isLoading, logout } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const badge = ROLE_COLORS[user?.role || ''] ?? ROLE_COLORS.ADMIN;

  return (
    <header
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '0 1.5rem',
        height: 'var(--navbar-height)',
        background: 'rgba(8, 12, 20, 0.9)',
        backdropFilter: 'blur(20px)',
        WebkitBackdropFilter: 'blur(20px)',
        borderBottom: '1px solid var(--border-subtle)',
        position: 'sticky',
        top: 0,
        zIndex: 50,
        marginBottom: '1.75rem',
      }}
      role="banner"
    >
      {/* Brand */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', flexShrink: 0 }}>
        <div
          style={{
            width: '36px', height: '36px', borderRadius: '10px',
            background: 'linear-gradient(135deg, #0f766e, #14b8a6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 14px rgba(20,184,166,0.35)',
            flexShrink: 0,
          }}
          aria-hidden="true"
        >
          <ShieldCheck size={19} color="#fff" />
        </div>
        <div>
          <div style={{ fontWeight: 800, fontSize: '0.95rem', letterSpacing: '-0.02em', color: '#fff', lineHeight: 1.2 }}>
            Edumerge Smart Attendance
          </div>
          <div style={{ fontSize: '0.68rem', color: 'var(--text-dim)', letterSpacing: '0.02em' }}>
            AI-Powered Academic Compliance System
          </div>
        </div>
      </div>

      {/* Desktop: User Info + Logout */}
      <div
        className="hide-mobile"
        style={{ display: 'flex', alignItems: 'center', gap: '0.875rem', flexShrink: 0 }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.55rem' }}>
          <div
            style={{
              width: '32px', height: '32px', borderRadius: '50%',
              background: badge.bg, border: `1px solid ${badge.border}`,
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
            aria-hidden="true"
          >
            <UserIcon size={15} color={badge.color} />
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: 'var(--text-main)', lineHeight: 1.2 }}>
              {user?.first_name} {user?.last_name || user?.username}
            </div>
            <span
              style={{
                display: 'inline-block', padding: '0.1rem 0.45rem',
                borderRadius: '4px', fontSize: '0.65rem', fontWeight: 700,
                background: badge.bg, color: badge.color, border: `1px solid ${badge.border}`,
                letterSpacing: '0.04em',
              }}
            >
              {user?.role}
            </span>
          </div>
        </div>

        <button
          className="btn btn-danger btn-sm"
          onClick={logout}
          title="Sign out"
          aria-label="Sign out of current session"
        >
          <LogOut size={13} />
          <span>Sign&nbsp;Out</span>
        </button>
      </div>

      {/* Mobile: hamburger */}
      <button
        style={{
          display: 'none',
          background: 'none', border: '1px solid var(--border-subtle)',
          color: 'var(--text-muted)', padding: '0.4rem', borderRadius: '8px', cursor: 'pointer',
        }}
        className="mobile-menu-btn"
        onClick={() => setMobileMenuOpen((v) => !v)}
        aria-label="Toggle menu"
        aria-expanded={mobileMenuOpen}
      >
        {mobileMenuOpen ? <X size={18} /> : <Menu size={18} />}
      </button>

      {/* Mobile Dropdown */}
      {mobileMenuOpen && (
        <div
          style={{
            position: 'absolute', top: 'var(--navbar-height)', left: 0, right: 0,
            background: 'rgba(8,12,20,0.97)', backdropFilter: 'blur(20px)',
            borderBottom: '1px solid var(--border-subtle)',
            padding: '1rem 1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem',
            zIndex: 49,
          }}
        >
          <button className="btn btn-danger btn-sm" onClick={logout} style={{ alignSelf: 'flex-start' }}>
            <LogOut size={13} /> Sign Out
          </button>
        </div>
      )}
    </header>
  );
};
