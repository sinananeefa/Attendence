import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';
import { api } from '../services/api';

interface Permissions {
  is_admin: boolean;
  is_hod: boolean;
  is_faculty: boolean;
  is_mentor: boolean;
  is_student: boolean;
}

interface AuthContextType {
  user: User | null;
  token: string | null;
  permissions: Permissions | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<boolean>;
  register: (payload: { username: string; email: string; password: string; password_confirm: string; first_name?: string; last_name?: string }) => Promise<boolean>;
  logout: () => void;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(localStorage.getItem('access_token'));
  const [permissions, setPermissions] = useState<Permissions | null>(() => {
    const saved = localStorage.getItem('user_permissions');
    return saved ? JSON.parse(saved) : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const initAuth = async () => {
      const savedToken = localStorage.getItem('access_token');
      if (savedToken) {
        try {
          const profile = await api.getMe(savedToken);
          setUser(profile.user);
          setPermissions(profile.permissions);
          localStorage.setItem('user_permissions', JSON.stringify(profile.permissions));
        } catch (err) {
          console.warn('Session expired or invalid token:', err);
          logout();
        }
      }
      setIsLoading(false);
    };
    initAuth();
  }, []);

  const login = async (username: string, password: string): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.login(username, password);
      setToken(res.access);
      setUser(res.user);
      setPermissions(res.permissions);

      localStorage.setItem('access_token', res.access);
      localStorage.setItem('refresh_token', res.refresh);
      localStorage.setItem('user_permissions', JSON.stringify(res.permissions));
      return true;
    } catch (err: any) {
      const msg = err.message || 'Login failed. Please check your credentials.';
      setError(msg);
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const register = async (payload: { username: string; email: string; password: string; password_confirm: string; first_name?: string; last_name?: string }): Promise<boolean> => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await api.register(payload);
      setToken(res.access);
      setUser(res.user);
      setPermissions(res.permissions);
      localStorage.setItem('access_token', res.access);
      localStorage.setItem('refresh_token', res.refresh);
      localStorage.setItem('user_permissions', JSON.stringify(res.permissions));
      return true;
    } catch (err: any) {
      setError(err.message || 'Account creation failed. Please review your details.');
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const logout = () => {
    setUser(null);
    setToken(null);
    setPermissions(null);
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    localStorage.removeItem('user_permissions');
  };

  const clearError = () => setError(null);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        permissions,
        isAuthenticated: !!user && !!token,
        isLoading,
        error,
        login,
        register,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within an AuthProvider');
  return context;
};
