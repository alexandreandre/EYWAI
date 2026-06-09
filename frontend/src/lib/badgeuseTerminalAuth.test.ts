import { beforeEach, describe, expect, it } from 'vitest';
import {
  clearTerminalSession,
  hasTerminalToken,
  isTerminalApiRequest,
  persistTerminalSession,
  readStoredTerminalSession,
} from '@/lib/badgeuseTerminalAuth';

function installFakeLocalStorage(): void {
  const store = new Map<string, string>();
  const fake: Storage = {
    get length() {
      return store.size;
    },
    clear: () => store.clear(),
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    key: (i: number) => Array.from(store.keys())[i] ?? null,
    removeItem: (k: string) => {
      store.delete(k);
    },
    setItem: (k: string, v: string) => {
      store.set(k, v);
    },
  };
  (globalThis as { localStorage: Storage }).localStorage = fake;
}

describe('badgeuseTerminalAuth', () => {
  beforeEach(() => {
    installFakeLocalStorage();
  });

  it('persiste puis relit une session complète (logo inclus)', () => {
    persistTerminalSession({
      token: '  tok-123  ',
      companyId: 'comp-1',
      label: 'iPad accueil',
      companyName: 'ACME',
      companyLogoUrl: 'https://cdn/acme.png',
    });

    const session = readStoredTerminalSession();
    expect(session).not.toBeNull();
    expect(session?.token).toBe('tok-123');
    expect(session?.companyId).toBe('comp-1');
    expect(session?.label).toBe('iPad accueil');
    expect(session?.companyName).toBe('ACME');
    expect(session?.companyLogoUrl).toBe('https://cdn/acme.png');
    expect(hasTerminalToken()).toBe(true);
  });

  it('clearTerminalSession purge tout, y compris le logo', () => {
    persistTerminalSession({
      token: 'tok',
      companyId: 'comp-1',
      companyLogoUrl: 'https://cdn/logo.png',
    });
    clearTerminalSession();

    expect(readStoredTerminalSession()).toBeNull();
    expect(hasTerminalToken()).toBe(false);
    expect(localStorage.getItem('badgeuseTerminalCompanyLogo')).toBeNull();
  });

  it('readStoredTerminalSession retourne null sans token/companyId', () => {
    expect(readStoredTerminalSession()).toBeNull();
  });

  it('isTerminalApiRequest détecte les routes terminal', () => {
    expect(isTerminalApiRequest('/api/badgeuse/terminal/status')).toBe(true);
    expect(isTerminalApiRequest('/api/badgeuse/dashboard/today')).toBe(false);
    expect(isTerminalApiRequest(undefined)).toBe(false);
  });
});
