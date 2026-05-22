import axios from 'axios';
import {
  clearAuthSession,
  getRefreshToken,
  persistAuthSession,
  type AuthSessionPayload,
} from '@/lib/authSession';
import { getApiBaseUrl } from './apiConfig';

let refreshInFlight: Promise<string | null> | null = null;

/**
 * Renouvelle le JWT via POST /api/auth/refresh (appel axios nu pour éviter les boucles d'intercepteurs).
 */
export async function refreshAccessToken(): Promise<string | null> {
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
    .catch(() => {
      clearAuthSession();
      return null;
    })
    .finally(() => {
      refreshInFlight = null;
    });

  return refreshInFlight;
}
