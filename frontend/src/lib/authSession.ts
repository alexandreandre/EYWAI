/**
 * Persistance locale de la session Supabase (access + refresh).
 * Le JWT d'accès expire en ~1 h ; le refresh token permet de le renouveler sans reconnecter l'utilisateur.
 */

const AUTH_TOKEN_KEY = 'authToken';
const REFRESH_TOKEN_KEY = 'refreshToken';
const EXPIRES_AT_KEY = 'authExpiresAt';

/** Renouveler ~5 min avant l'expiration du JWT. */
export const REFRESH_MARGIN_MS = 5 * 60 * 1000;

export interface AuthSessionPayload {
  access_token: string;
  refresh_token?: string | null;
  expires_at?: number | null;
  expires_in?: number | null;
}

export function persistAuthSession(payload: AuthSessionPayload): void {
  const access = payload.access_token?.trim();
  if (!access) return;

  localStorage.setItem(AUTH_TOKEN_KEY, access);

  if (payload.refresh_token) {
    localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  }

  let expiresAt = payload.expires_at ?? null;
  if (!expiresAt && payload.expires_in) {
    expiresAt = Math.floor(Date.now() / 1000) + payload.expires_in;
  }
  if (expiresAt) {
    localStorage.setItem(EXPIRES_AT_KEY, String(expiresAt));
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(AUTH_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function getExpiresAt(): number | null {
  const raw = localStorage.getItem(EXPIRES_AT_KEY);
  if (!raw) return null;
  const n = Number(raw);
  return Number.isFinite(n) ? n : null;
}

export function clearAuthSession(): void {
  localStorage.removeItem(AUTH_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(EXPIRES_AT_KEY);
}

/** True si le JWT est absent, expiré, ou expire bientôt. */
export function shouldRefreshAccessToken(): boolean {
  const expiresAt = getExpiresAt() ?? decodeJwtExp(getAccessToken());
  if (!expiresAt) return false;
  return Date.now() >= expiresAt * 1000 - REFRESH_MARGIN_MS;
}

function decodeJwtExp(token: string | null): number | null {
  if (!token) return null;
  const parts = token.split('.');
  if (parts.length < 2) return null;
  try {
    const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/'))) as {
      exp?: unknown;
    };
    return typeof payload.exp === 'number' ? payload.exp : null;
  } catch {
    return null;
  }
}

export function hasRefreshToken(): boolean {
  return Boolean(getRefreshToken());
}
