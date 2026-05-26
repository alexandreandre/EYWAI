// src/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { refreshAccessToken } from '@/api/authRefresh';
import {
  clearAuthSession,
  getAccessToken,
  getExpiresAt,
  hasRefreshToken,
  persistAuthSession,
  REFRESH_MARGIN_MS,
  shouldRefreshAccessToken,
  type AuthSessionPayload,
} from '@/lib/authSession';
import { CompanyAccess } from "./CompanyContext";

// === Types ===

interface User {
  id: string;
  email: string;
  role?: 'rh' | 'collaborateur' | 'collaborateur_rh' | 'admin' | 'super_admin' | 'custom';
  first_name: string;
  last_name?: string;
  is_super_admin?: boolean;
  is_group_admin?: boolean;
  active_company?: CompanyAccess;
}

interface AuthContextType {
  user: User | null;
  login: (session: AuthSessionPayload) => Promise<void>;
  logout: () => Promise<void>;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function normalizeUser(u: Record<string, unknown>): User {
  const role =
    (u.role as User['role']) ||
    (u.active_company as CompanyAccess | undefined)?.role ||
    null;

  return {
    ...(u as unknown as User),
    role: role ?? undefined,
  };
}

function applyAccessToken(token: string): void {
  const clean = token.startsWith('Bearer ') ? token.split(' ')[1] : token;
  const authHeader = `Bearer ${clean}`;
  apiClient.defaults.headers.common['Authorization'] = authHeader;
}

async function fetchCurrentUser(): Promise<User> {
  const token = getAccessToken();
  const response = await apiClient.get('/api/auth/me', {
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  return normalizeUser(response.data);
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const refreshTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const scheduleSilentRefresh = () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }
    if (!hasRefreshToken()) return;

    const expiresAt = getExpiresAt();
    if (!expiresAt) return;

    const delay = expiresAt * 1000 - Date.now() - REFRESH_MARGIN_MS;
    const waitMs = delay > 0 ? delay : 0;

    refreshTimerRef.current = setTimeout(async () => {
      const newToken = await refreshAccessToken();
      if (newToken) {
        applyAccessToken(newToken);
        scheduleSilentRefresh();
      }
    }, waitMs);
  };

  useEffect(() => {
    let cancelled = false;

    const restoreSession = async () => {
      const token = getAccessToken();
      if (!token) {
        setIsLoading(false);
        return;
      }

      applyAccessToken(token);

      try {
        if (shouldRefreshAccessToken() && hasRefreshToken()) {
          const renewed = await refreshAccessToken();
          if (renewed) {
            applyAccessToken(renewed);
          }
        }

        const me = await fetchCurrentUser();
        if (!cancelled) {
          setUser(me);
          scheduleSilentRefresh();
        }
      } catch {
        if (hasRefreshToken()) {
          const renewed = await refreshAccessToken();
          if (renewed) {
            try {
              applyAccessToken(renewed);
              const me = await fetchCurrentUser();
              if (!cancelled) {
                setUser(me);
                scheduleSilentRefresh();
                return;
              }
            } catch {
              /* pass */
            }
          }
        }
        if (!cancelled) {
          clearAuthSession();
          delete apiClient.defaults.headers.common['Authorization'];
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void restoreSession();

    return () => {
      cancelled = true;
      if (refreshTimerRef.current) {
        clearTimeout(refreshTimerRef.current);
      }
    };
  }, []);

  const login = async (session: AuthSessionPayload) => {
    persistAuthSession(session);
    applyAccessToken(session.access_token);

    try {
      const me = await fetchCurrentUser();
      setUser(me);
      scheduleSilentRefresh();
    } catch (error) {
      await logout();
      throw error;
    }
  };

  const logout = async () => {
    if (refreshTimerRef.current) {
      clearTimeout(refreshTimerRef.current);
      refreshTimerRef.current = null;
    }

    try {
      await apiClient.post('/api/auth/logout');
    } catch {
      /* déconnexion locale même si le backend échoue */
    }

    queryClient.clear();
    setUser(null);
    clearAuthSession();
    delete apiClient.defaults.headers.common['Authorization'];
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, isLoading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within an AuthProvider");
  return ctx;
};

export function hasRhAccess(user: User | null, companyId: string): boolean {
  if (!user) return false;
  if (user.is_super_admin) return true;
  if (user.role === 'rh' || user.role === 'collaborateur_rh' || user.role === 'admin') {
    return true;
  }
  if (user.role === 'custom') {
    return false;
  }
  return false;
}

export function isCollaborateurRh(user: User | null): boolean {
  if (!user) return false;
  return user.role === 'collaborateur_rh';
}
