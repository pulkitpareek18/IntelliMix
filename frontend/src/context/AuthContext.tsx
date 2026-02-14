import React, { createContext, useCallback, useEffect, useMemo, useState } from 'react';
import {
  ENDPOINTS,
  apiRequest,
  clearAuthTokens,
  getAccessToken,
  getRefreshToken,
  setAuthTokens,
} from '../utils/api';

export interface AuthUser {
  id: string;
  name: string;
  email: string;
  created_at: string;
}

interface AuthResponse {
  user: AuthUser;
  access_token: string;
  refresh_token: string;
}

export interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (name: string, email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    const response = await apiRequest<{ user: AuthUser }>(ENDPOINTS.AUTH_ME, {
      method: 'GET',
    });
    setUser(response.user);
  }, []);

  useEffect(() => {
    const bootstrap = async () => {
      if (!getAccessToken() && !getRefreshToken()) {
        setLoading(false);
        return;
      }

      try {
        await refreshUser();
      } catch {
        clearAuthTokens();
        setUser(null);
      } finally {
        setLoading(false);
      }
    };

    bootstrap();
  }, [refreshUser]);

  const login = useCallback(async (email: string, password: string) => {
    const response = await apiRequest<AuthResponse>(
      ENDPOINTS.AUTH_LOGIN,
      {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      },
      { auth: false, retryOnUnauthorized: false }
    );

    setAuthTokens(response.access_token, response.refresh_token);
    setUser(response.user);
  }, []);

  const signup = useCallback(async (name: string, email: string, password: string) => {
    const response = await apiRequest<AuthResponse>(
      ENDPOINTS.AUTH_REGISTER,
      {
        method: 'POST',
        body: JSON.stringify({ name, email, password }),
      },
      { auth: false, retryOnUnauthorized: false }
    );

    setAuthTokens(response.access_token, response.refresh_token);
    setUser(response.user);
  }, []);

  const logout = useCallback(async () => {
    const refreshToken = getRefreshToken();

    try {
      await apiRequest<{ message: string }>(
        ENDPOINTS.AUTH_LOGOUT,
        {
          method: 'POST',
          body: JSON.stringify({ refresh_token: refreshToken }),
        },
        {
          auth: true,
          retryOnUnauthorized: false,
        }
      );
    } catch {
      // Token might already be expired/revoked; clear local auth state regardless.
    } finally {
      clearAuthTokens();
      setUser(null);
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      loading,
      isAuthenticated: Boolean(user),
      login,
      signup,
      logout,
      refreshUser,
    }),
    [user, loading, login, signup, logout, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
