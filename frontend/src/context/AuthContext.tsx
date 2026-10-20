import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { User, AuthStatusResponse } from '@/types';
import { apiService } from '@/lib/api-services';
import { getStoredAuthToken, setStoredAuthToken } from '@/lib/api-client';

interface AuthContextType {
  user: User | null;
  token: string | null;
  authStatus: AuthStatusResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  error: string | null;
  loginWithGoogle: (idToken: string) => Promise<void>;
  devLogin: (email?: string, name?: string) => Promise<void>;
  logout: () => Promise<void>;
  clearError: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => getStoredAuthToken());
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Synchronize initial session and backend auth status
  useEffect(() => {
    let isMounted = true;

    async function initializeAuth() {
      try {
        const status = await apiService.getAuthStatus();
        if (!isMounted) return;
        setAuthStatus(status);

        if (!status.auth_enabled) {
          // Auth gateway is disabled in backend config: authenticate automatically with dev user
          try {
            const devMe = await apiService.getMe();
            if (isMounted) setUser(devMe);
          } catch {
            if (isMounted) {
              setUser({
                user_id: 'dev-user',
                email: 'organizer@recruitment.local',
                full_name: 'Lead Organizer (Auth Disabled)',
                role: 'user',
                is_active: true,
                created_at: new Date().toISOString(),
              });
            }
          }
        } else {
          // Auth is enabled: check if we have a valid stored token
          const existingToken = getStoredAuthToken();
          if (existingToken) {
            try {
              const currentUser = await apiService.getMe();
              if (isMounted) setUser(currentUser);
            } catch (err) {
              // Token invalid or expired
              if (isMounted) {
                setStoredAuthToken(null);
                setToken(null);
                setUser(null);
              }
            }
          }
        }
      } catch (err: any) {
        console.error('Failed to initialize auth status:', err);
        if (isMounted) {
          // If status fails, assume offline or fallback
          setError(err?.message || 'Failed to connect to authentication service');
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    initializeAuth();

    // Listen for 401 unauthorized events dispatched by api-client
    const handleUnauthorized = () => {
      setStoredAuthToken(null);
      setToken(null);
      setUser(null);
    };

    window.addEventListener('auth:unauthorized', handleUnauthorized);
    return () => {
      isMounted = false;
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, []);

  const loginWithGoogle = useCallback(async (idToken: string) => {
    setError(null);
    try {
      const resp = await apiService.loginWithGoogle(idToken);
      setStoredAuthToken(resp.access_token);
      setToken(resp.access_token);
      setUser(resp.user);
    } catch (err: any) {
      const msg = err?.message || 'Google authentication failed';
      setError(msg);
      throw err;
    }
  }, []);

  const devLogin = useCallback(async (email?: string, name?: string) => {
    setError(null);
    try {
      const resp = await apiService.devLogin(email, name);
      setStoredAuthToken(resp.access_token);
      setToken(resp.access_token);
      setUser(resp.user);
    } catch (err: any) {
      const msg = err?.message || 'Developer login failed';
      setError(msg);
      throw err;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await apiService.logout();
    } catch (err) {
      console.warn('Backend logout encountered non-fatal error:', err);
    } finally {
      setStoredAuthToken(null);
      setToken(null);
      setUser(null);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  const isAuthenticated = !authStatus?.auth_enabled || !!user;

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        authStatus,
        isLoading,
        isAuthenticated,
        error,
        loginWithGoogle,
        devLogin,
        logout,
        clearError,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
