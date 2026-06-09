import { useCallback, useEffect, useState } from 'react';
import { isAxiosError } from 'axios';
import { getTerminalStatus } from '@/api/badgeuseTerminal';
import {
  clearTerminalSession,
  consumeSetupTokenFromUrl,
  hasTerminalToken,
  persistTerminalSession,
  readStoredTerminalSession,
  type BadgeuseTerminalSession,
} from '@/lib/badgeuseTerminalAuth';

/** 401/403 = jeton terminal révoqué ou invalide → échec définitif. */
function isDefinitiveTerminalAuthFailure(error: unknown): boolean {
  if (!isAxiosError(error)) return false;
  const status = error.response?.status;
  return status === 401 || status === 403;
}

function readSetupTokenFromUrl(): string | null {
  if (typeof window === 'undefined') return null;
  return new URLSearchParams(window.location.search).get('setup')?.trim() || null;
}

function getInitialTerminalAuthState(): {
  session: BadgeuseTerminalSession | null;
  isValid: boolean;
  isLoading: boolean;
} {
  const setupToken = readSetupTokenFromUrl();
  if (setupToken) {
    return {
      session: { token: setupToken, companyId: 'pending' },
      isValid: false,
      isLoading: true,
    };
  }

  const stored = readStoredTerminalSession();
  if (stored) {
    return {
      session: stored,
      isValid: true,
      isLoading: false,
    };
  }

  return {
    session: null,
    isValid: false,
    isLoading: false,
  };
}

export type BadgeuseTerminalAuthMode = 'none' | 'terminal' | 'rh';

export interface BadgeuseTerminalAuthState {
  mode: BadgeuseTerminalAuthMode;
  isLoading: boolean;
  isValid: boolean;
  session: BadgeuseTerminalSession | null;
  error: string | null;
  refresh: () => Promise<void>;
}

export function useBadgeuseTerminalAuth(
  hasRhUser: boolean,
): BadgeuseTerminalAuthState {
  const initial = getInitialTerminalAuthState();
  const [isLoading, setIsLoading] = useState(initial.isLoading);
  const [isValid, setIsValid] = useState(initial.isValid);
  const [session, setSession] = useState<BadgeuseTerminalSession | null>(
    initial.session,
  );
  const [error, setError] = useState<string | null>(null);

  const validateTerminal = useCallback(async (tokenOverride?: string) => {
    const setupToken = tokenOverride ?? consumeSetupTokenFromUrl();
    if (setupToken) {
      persistTerminalSession({ token: setupToken, companyId: 'pending' });
    }

    if (!hasTerminalToken() && !setupToken) {
      setSession(null);
      setIsValid(false);
      setError(null);
      setIsLoading(false);
      return;
    }

    const hadCachedSession = Boolean(readStoredTerminalSession()) && !setupToken;
    if (!hadCachedSession) {
      setIsLoading(true);
    }
    setError(null);

    try {
      const status = await getTerminalStatus();
      const nextSession: BadgeuseTerminalSession = {
        token: readStoredTerminalSession()?.token ?? setupToken ?? '',
        companyId: status.company_id,
        label: status.label,
        companyName: status.company_name ?? undefined,
        companyLogoUrl: status.logo_url ?? undefined,
      };
      persistTerminalSession(nextSession);
      setSession(nextSession);
      setIsValid(true);
    } catch (err) {
      setIsValid(false);
      if (isDefinitiveTerminalAuthFailure(err)) {
        clearTerminalSession();
        setSession(null);
        setError('Jeton terminal invalide ou révoqué');
      } else if (hadCachedSession) {
        setSession(readStoredTerminalSession());
        setError('Connexion au terminal impossible. Réessayez.');
      } else {
        setSession(readStoredTerminalSession());
        setError('Connexion au terminal impossible. Réessayez.');
      }
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void validateTerminal();
  }, [validateTerminal]);

  const mode: BadgeuseTerminalAuthMode = isValid
    ? 'terminal'
    : hasRhUser
      ? 'rh'
      : 'none';

  return {
    mode,
    isLoading,
    isValid,
    session,
    error,
    refresh: validateTerminal,
  };
}
