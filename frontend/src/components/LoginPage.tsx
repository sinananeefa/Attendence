import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { 
  ShieldCheck, Lock, User as UserIcon, AlertCircle, ArrowRight, UserPlus, KeyRound
} from 'lucide-react';

const demoCredentials = [
  { label: 'Administrator', username: 'admin', password: 'Admin@123' },
  { label: 'Faculty', username: 'fac_priya', password: 'Faculty@123' },
  { label: 'Student', username: '24cse001', password: 'Student@123' },
];

export const LoginPage: React.FC = () => {
  const { login, register, error, clearError, isLoading } = useAuth();
  const [isRegistering, setIsRegistering] = useState(false);
  const [username, setUsername] = useState(() => localStorage.getItem('last_login_identifier') || (import.meta.env.DEV ? 'admin' : ''));
  const [rememberIdentifier, setRememberIdentifier] = useState(() => localStorage.getItem('remember_login_identifier') === 'true');
  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [password, setPassword] = useState(import.meta.env.DEV ? 'Admin@123' : '');
  const [passwordConfirm, setPasswordConfirm] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isRegistering) {
      await register({ username, email, password, password_confirm: passwordConfirm, first_name: firstName, last_name: lastName });
    } else if (username && password) {
      const authenticated = await login(username, password);
      if (authenticated && rememberIdentifier) {
        localStorage.setItem('last_login_identifier', username);
        localStorage.setItem('remember_login_identifier', 'true');
      } else if (authenticated) {
        localStorage.removeItem('last_login_identifier');
        localStorage.removeItem('remember_login_identifier');
      }
    }
  };

  const fillDemoCredential = (credential: typeof demoCredentials[number]) => {
    setIsRegistering(false);
    setUsername(credential.username);
    setPassword(credential.password);
    clearError();
  };

  return (
    <div className="login-page">
      {/* Header */}
      <div style={{ textAlign: 'center', marginBottom: '2.5rem' }}>
        <div className="header-badge" style={{ marginBottom: '0.75rem' }}>
          <ShieldCheck size={14} />
          Edumerge &mdash; Secure Institutional Portal
        </div>
        <h1 className="hero-title" style={{ fontSize: '2.4rem' }}>
          Sign In to Your Account
        </h1>
        <p className="hero-subtitle" style={{ margin: '0 auto' }}>
          Role-based access for students, faculty, and administrators.
          Permissions are enforced server-side via JWT tokens.
        </p>
      </div>

      <div className="login-layout">
        {/* Login Form */}
        <div className="glass-panel login-form-panel" style={{ padding: '2rem' }}>
          <h2 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <Lock size={18} color="var(--accent-cyan)" />
            {isRegistering ? 'Create your student account' : 'Sign In with Institutional ID'}
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '1.5rem' }}>
            {isRegistering ? 'Create an account to access your student attendance workspace.' : 'Use your institutional credentials to access the attendance workspace.'}
          </p>

          {error && (
            <div style={{
              background: 'rgba(244, 63, 94, 0.12)',
              border: '1px solid rgba(244, 63, 94, 0.3)',
              borderRadius: '8px',
              padding: '0.85rem 1rem',
              color: '#fda4af',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
              marginBottom: '1.25rem'
            }}>
              <AlertCircle size={16} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '1.2rem' }}>
            {isRegistering && (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>First name</label>
                  <input type="text" value={firstName} onChange={(e) => { setFirstName(e.target.value); clearError(); }} placeholder="First name" autoComplete="given-name" className="form-input" />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>Last name</label>
                  <input type="text" value={lastName} onChange={(e) => { setLastName(e.target.value); clearError(); }} placeholder="Last name" autoComplete="family-name" className="form-input" />
                </div>
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
                Username / Email / Roll Number
              </label>
              <div style={{ position: 'relative' }}>
                <UserIcon size={16} style={{ position: 'absolute', left: '12px', top: '13px', color: 'var(--text-dim)' }} />
                <input
                  id="login-username"
                  type="text"
                  value={username}
                  onChange={(e) => { setUsername(e.target.value); clearError(); }}
                  placeholder="e.g. admin, fac_priya, 24cse001"
                  required
                  autoComplete="username"
                  aria-label="Username, email, or roll number"
                  className="form-input"
                  style={{ paddingLeft: '2.4rem' }}
                />
              </div>
            </div>

            {!isRegistering && (
              <label className="remember-login">
                <input
                  type="checkbox"
                  checked={rememberIdentifier}
                  onChange={(e) => setRememberIdentifier(e.target.checked)}
                />
                Remember my username or email on this device
              </label>
            )}

            {isRegistering && (
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>Email</label>
                <input id="register-email" type="email" value={email} onChange={(e) => { setEmail(e.target.value); clearError(); }} placeholder="you@institution.edu" required autoComplete="email" aria-label="Email" className="form-input" />
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>
                Password
              </label>
              <div style={{ position: 'relative' }}>
                <Lock size={16} style={{ position: 'absolute', left: '12px', top: '13px', color: 'var(--text-dim)' }} />
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); clearError(); }}
                  placeholder="Enter your password"
                  required
                  autoComplete="current-password"
                  aria-label="Password"
                  className="form-input"
                  style={{ paddingLeft: '2.4rem' }}
                />
              </div>
            </div>

            {isRegistering && (
              <div>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-dim)', marginBottom: '0.4rem', textTransform: 'uppercase' }}>Confirm password</label>
                <input id="register-password-confirm" type="password" value={passwordConfirm} onChange={(e) => { setPasswordConfirm(e.target.value); clearError(); }} placeholder="Re-enter your password" required autoComplete="new-password" aria-label="Confirm password" className="form-input" style={{ paddingLeft: '2.4rem' }} />
              </div>
            )}

            <button
              type="submit"
              disabled={isLoading}
              className="btn btn-primary btn-lg"
              style={{ marginTop: '0.5rem', width: '100%' }}
            >
              {isLoading ? (
                <><span className="spinner spinner-sm" /> {isRegistering ? 'Creating account…' : 'Verifying…'}</>
              ) : (
                <>{isRegistering ? 'Create account' : 'Authenticate & Sign In'} {isRegistering ? <UserPlus size={15} /> : <ArrowRight size={15} />}</>
              )}
            </button>
          </form>

          <button
            type="button"
            className="btn btn-ghost"
            style={{ width: '100%', marginTop: '1rem' }}
            onClick={() => { setIsRegistering(!isRegistering); clearError(); }}
          >
            {isRegistering ? 'Already have an account? Sign in' : 'Need an account? Create one'}
          </button>
        </div>

        {/* Account access guidance */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="glass-panel login-guidance-panel" style={{ padding: '1.25rem' }}>
            <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#60a5fa' }}>
              <Lock size={16} />
              Account access
            </h3>
            <p style={{ color: 'var(--text-muted)', fontSize: '0.8rem', lineHeight: 1.5 }}>
              Access is based on your assigned account and server-side permissions. Contact your institution administrator if you need an account or password reset.
            </p>
          </div>
          {import.meta.env.DEV && (
            <div className="glass-panel login-demo-panel" style={{ padding: '1.25rem' }}>
              <h3 style={{ fontSize: '0.95rem', fontWeight: 700, marginBottom: '0.35rem', display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#67e8f9' }}>
                <KeyRound size={16} />
                Demo access
              </h3>
              <p style={{ color: 'var(--text-muted)', fontSize: '0.78rem', lineHeight: 1.5, marginBottom: '0.8rem' }}>
                Development accounts only. Select a role to fill the sign-in form.
              </p>
              <div className="login-demo-list">
                {demoCredentials.map((credential) => (
                  <button
                    key={credential.username}
                    type="button"
                    className="login-demo-button"
                    onClick={() => fillDemoCredential(credential)}
                  >
                    <span>{credential.label}</span>
                    <small>{credential.username}</small>
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
