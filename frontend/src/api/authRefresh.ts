import axios, { isAxiosError } from 'axios';
import {
  clearAuthSession,
  getRefreshToken,
  persistAuthSession,
  type AuthSessionPayload,
} from '@/lib/authSession';
import { getApiBaseUrl } from './apiConfig';

let refreshInFlight: Promise<string | null> | null = null;

export interface RefreshAccessTokenOptions {
  /** Efface la session locale uniquement en cas d'échec définitif (401). */
  clearOnFailure?: boolean;
}

function isDefinitiveRefreshFailure(error: unknown): boolean {
  if (!isAxiosError(error)) return false;
  const status = error.response?.status;
  return status === 401 || status === 403;
}

/**
 * Renouvelle le JWT via POST /api/auth/refresh (appel axios nu pour éviter les boucles d'intercepteurs).
 */
export async function refreshAccessToken(
  options: RefreshAccessTokenOptions = {},
): Promise<string | null> {
  const { clearOnFailure = true } = options;
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  if (refreshInFlight) {
    return refreshInFlight;
  }

  const baseUrl = getApiBaseUrl();
  refreshInFlight = axios
    .post<AuthSessionPayload>(`${baseUrl}/api/auth/refresh`, {
      refresh_token: refreshToken,
    })
    .then((res) => {
      const data = res.data;
      if (!data?.access_token) return null;
      persistAuthSession(data);
      return data.access_token;
    })
    .catch((error) => {
      if (clearOnFailure && isDefinitiveRefreshFailure(error)) {
        clearAuthSession();
      }
      return null;
    })
    .finally(() => {
      refreshInFlight = null;
    });

  return refreshInFlight;
}
