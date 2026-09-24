import React from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import { ToastProvider } from './components/Toast';
import { Navbar } from './components/Navbar';
import { LoginPage } from './components/LoginPage';
import { AdminDashboard } from './components/AdminDashboard';
import { FacultyDashboard } from './components/FacultyDashboard';
import { StudentDashboard } from './components/StudentDashboard';
import { Shield } from 'lucide-react';
import './styles/theme.css';

const MainAppContent: React.FC = () => {
  const { user, isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          height: '100vh',
          gap: '1rem',
        }}
        role="status"
        aria-live="polite"
      >
        <div
          style={{
            width: '48px', height: '48px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #0f766e, #14b8a6)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 6px 20px rgba(20,184,166,0.4)',
          }}
        >
          <Shield size={24} color="#fff" />
        </div>
        <div className="spinner spinner-lg" />
        <span style={{ color: 'var(--text-muted)', fontSize: '0.9rem' }}>Authenticating session…</span>
      </div>
    );
  }

  if (!isAuthenticated || !user) {
    return <LoginPage />;
  }

  return (
    <div>
      <Navbar />

      <main className="app-container" style={{ paddingTop: '0' }}>
        {/* Role-based Dashboard */}
        <div className="animate-in">
          {user.role === 'ADMIN'                                               && <AdminDashboard />}
          {(user.role === 'FACULTY' || user.role === 'HOD' || user.role === 'MENTOR') && <FacultyDashboard />}
          {user.role === 'STUDENT'                                             && <StudentDashboard />}
        </div>
      </main>
    </div>
  );
};

export const App: React.FC = () => (
  <AuthProvider>
    <ToastProvider>
      <MainAppContent />
    </ToastProvider>
  </AuthProvider>
);
