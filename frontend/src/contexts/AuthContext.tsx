// src/contexts/AuthContext.tsx
import { createContext, useContext, useState, useEffect, useRef, ReactNode } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import apiClient from '@/api/apiClient';
import { refreshAccessToken } from '@/api/authRefresh';
import {
  clearAuthSession,
  getAccessToken,
  hasRefreshToken,
  persistAuthSession,
  shouldRefreshAccessToken,
  type AuthSessionPayload,
} from '@/lib/authSession';
import { startSessionKeepAlive, isBadgeuseTerminalPath } from '@/lib/sessionKeepAlive';
import { hasTerminalToken } from '@/lib/badgeuseTerminalAuth';
import { CompanyAccess } from "./CompanyContext";
import { useBootOptional } from '@/contexts/BootContext';
import { isPlatformAdmin } from '@/lib/platformAdmin';

// === Types ===

interface User {
  id: string;
  email: string;
  role?: 'rh' | 'collaborateur' | 'collaborateur_rh' | 'admin' | 'custom';
  first_name: string;
  last_name?: string;
  is_platform_admin?: boolean;
  /** @deprecated — utiliser is_platform_admin */
  is_super_admin?: boolean;
  is_group_admin?: boolean;
  active_company?: CompanyAccess;
}

interface AuthContextType {
  user: User | null;
  login: (session: AuthSessionPayload) => Promise<User>;
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
  const requestMe = async () => {
    const token = getAccessToken();
    const response = await apiClient.get('/api/auth/me', {
      headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    });
    return normalizeUser(response.data);
  };

  try {
    return await requestMe();
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 401 && hasRefreshToken()) {
      const renewed = await refreshAccessToken();
      if (renewed) {
        applyAccessToken(renewed);
        return await requestMe();
      }
    }
    throw error;
  }
}

export const AuthProvider = ({ children }: { children: ReactNode }) => {
  const queryClient = useQueryClient();
  const boot = useBootOptional();
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const stopKeepAliveRef = useRef<(() => void) | null>(null);

  const startKeepAlive = () => {
    stopKeepAliveRef.current?.();
    stopKeepAliveRef.current = startSessionKeepAlive({
      onRefreshed: applyAccessToken,
    });
  };

  const stopKeepAlive = () => {
    stopKeepAliveRef.current?.();
    stopKeepAliveRef.current = null;
  };

  useEffect(() => {
    let cancelled = false;

    const restoreSession = async () => {
      const token = getAccessToken();
      const terminalKiosk = isBadgeuseTerminalPath() && hasTerminalToken();

      if (!token) {
        setIsLoading(false);
        return;
      }

      applyAccessToken(token);

      if (terminalKiosk) {
        setIsLoading(false);
        void (async () => {
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
              startKeepAlive();
            }
          } catch {
            /* La badgeuse kiosque fonctionne sans session RH. */
          }
        })();
        return;
      }

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
          startKeepAlive();
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
                startKeepAlive();
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
      stopKeepAlive();
    };
  }, []);

  const login = async (session: AuthSessionPayload): Promise<User> => {
    boot?.resetBoot();
    persistAuthSession(session);
    applyAccessToken(session.access_token);

    try {
      const me = await fetchCurrentUser();
      setUser(me);
      startKeepAlive();
      return me;
    } catch (error) {
      await logout();
      throw error;
    }
  };

  const logout = async () => {
    boot?.resetBoot();
    stopKeepAlive();

    try {
      await apiClient.post('/api/auth/logout');
    } catch {
      /* déconnexion locale même si le backend échoue */
    }

    queryClient.clear();
    setUser(null);
    clearAuthSession();
    delete apiClient.defaults.headers.common['Authorization'];
    window.location.assign('/login');
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
  if (isPlatformAdmin(user)) return true;
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
