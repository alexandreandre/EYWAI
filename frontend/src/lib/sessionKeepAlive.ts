/**
 * Maintien de session actif tant que l'onglet reste ouvert.
 *
 * Pratiques classiques SPA / kiosque :
 * - refresh proactif périodique (sliding session via refresh token)
 * - contrôle fréquent de l'expiration du JWT
 * - refresh au retour de visibilité (onglet réveillé après veille navigateur)
 * - refresh au retour réseau
 * - retries sur erreur réseau transitoire (Wi‑Fi usine)
 */

import { refreshAccessToken } from '@/api/authRefresh';
import {
  getExpiresAt,
  hasRefreshToken,
  REFRESH_MARGIN_MS,
  shouldRefreshAccessToken,
} from '@/lib/authSession';
import { BADGEUSE_RH_TERMINAL_PATH } from '@/lib/badgeuseRoutes';

export type SessionKeepAliveMode = 'default' | 'kiosk';

export interface SessionKeepAliveOptions {
  mode?: SessionKeepAliveMode;
  onRefreshed?: (accessToken: string) => void;
}

const DEFAULT_PROACTIVE_MS = 45 * 60 * 1000;
const KIOSK_PROACTIVE_MS = 25 * 60 * 1000;
const DEFAULT_CHECK_MS = 60 * 1000;
const KIOSK_CHECK_MS = 30 * 1000;
const MAX_REFRESH_RETRIES = 5;
const RETRY_BASE_MS = 2_000;

export function isBadgeuseTerminalPath(pathname = window.location.pathname): boolean {
  return (
    pathname === BADGEUSE_RH_TERMINAL_PATH ||
    pathname === '/badgeuse-rh/scan'
  );
}

export function resolveSessionKeepAliveMode(
  pathname = window.location.pathname,
): SessionKeepAliveMode {
  return isBadgeuseTerminalPath(pathname) ? 'kiosk' : 'default';
}

/** Intervalle entre deux refresh proactifs (même si le JWT est encore valide). */
export function proactiveRefreshIntervalMs(mode: SessionKeepAliveMode): number {
  return mode === 'kiosk' ? KIOSK_PROACTIVE_MS : DEFAULT_PROACTIVE_MS;
}

/** Fréquence de vérification de l'expiration imminente du JWT. */
export function sessionCheckIntervalMs(mode: SessionKeepAliveMode): number {
  return mode === 'kiosk' ? KIOSK_CHECK_MS : DEFAULT_CHECK_MS;
}

export function shouldRunProactiveRefresh(
  lastRefreshAt: number | null,
  now: number,
  intervalMs: number,
): boolean {
  if (!lastRefreshAt) return true;
  return now - lastRefreshAt >= intervalMs;
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, ms);
  });
}

async function refreshWithRetry(clearOnFinalFailure: boolean): Promise<string | null> {
  for (let attempt = 0; attempt < MAX_REFRESH_RETRIES; attempt += 1) {
    const isLastAttempt = attempt === MAX_REFRESH_RETRIES - 1;
    const token = await refreshAccessToken({
      clearOnFailure: clearOnFinalFailure && isLastAttempt,
    });
    if (token) return token;
    if (!hasRefreshToken()) return null;
    if (!isLastAttempt) {
      await sleep(RETRY_BASE_MS * 2 ** attempt);
    }
  }
  return null;
}

async function runRefreshIfNeeded(
  options: SessionKeepAliveOptions,
  force = false,
): Promise<void> {
  if (!hasRefreshToken()) return;
  if (!force && !shouldRefreshAccessToken()) return;

  const token = await refreshWithRetry(true);
  if (token) {
    options.onRefreshed?.(token);
  }
}

/**
 * Démarre le maintien de session. Retourne une fonction de nettoyage.
 * À appeler dès qu'une session utilisateur est établie.
 */
export function startSessionKeepAlive(
  options: SessionKeepAliveOptions = {},
): () => void {
  let lastProactiveRefreshAt = Date.now();
  let disposed = false;

  const resolveMode = (): SessionKeepAliveMode =>
    options.mode ?? resolveSessionKeepAliveMode();

  const tick = async (force = false) => {
    if (disposed) return;

    const mode = resolveMode();
    const proactiveMs = proactiveRefreshIntervalMs(mode);
    const now = Date.now();
    const proactiveDue = shouldRunProactiveRefresh(
      lastProactiveRefreshAt,
      now,
      proactiveMs,
    );

    if (force || proactiveDue || shouldRefreshAccessToken()) {
      const before = getExpiresAt();
      await runRefreshIfNeeded(options, force || proactiveDue);
      if (!disposed && (force || proactiveDue || getExpiresAt() !== before)) {
        lastProactiveRefreshAt = Date.now();
      }
    }
  };

  const onVisibilityChange = () => {
    if (document.visibilityState === 'visible') {
      void tick(true);
    }
  };

  const onWindowFocus = () => {
    void tick(true);
  };

  const onOnline = () => {
    void tick(true);
  };

  const checkTimer = window.setInterval(() => {
    void tick(false);
  }, KIOSK_CHECK_MS);

  const proactiveTimer = window.setInterval(() => {
    void tick(true);
  }, KIOSK_PROACTIVE_MS);

  document.addEventListener('visibilitychange', onVisibilityChange);
  window.addEventListener('focus', onWindowFocus);
  window.addEventListener('online', onOnline);

  void tick(true);

  return () => {
    disposed = true;
    window.clearInterval(checkTimer);
    window.clearInterval(proactiveTimer);
    document.removeEventListener('visibilitychange', onVisibilityChange);
    window.removeEventListener('focus', onWindowFocus);
    window.removeEventListener('online', onOnline);
  };
}
