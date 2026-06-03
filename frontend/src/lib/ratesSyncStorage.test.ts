import { describe, expect, it, beforeEach, vi } from 'vitest';

import {
  readPersistedSyncIds,
  readPersistedSyncSessions,
  removePersistedSyncId,
  writePersistedSyncSessions,
} from '@/lib/ratesSyncStorage';

describe('ratesSyncStorage', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal('sessionStorage', {
      getItem: (key: string) => store.get(key) ?? null,
      setItem: (key: string, value: string) => {
        store.set(key, value);
      },
      removeItem: (key: string) => {
        store.delete(key);
      },
      clear: () => {
        store.clear();
      },
    });
  });

  it('persiste la cible et la date de début', () => {
    writePersistedSyncSessions([
      {
        syncId: 'abc-123',
        target: { scope: 'rate_key', rateKey: 'pss' },
        isMonthly: false,
        createdAt: '2026-05-28T10:00:00.000Z',
      },
    ]);

    const sessions = readPersistedSyncSessions();
    expect(sessions).toHaveLength(1);
    expect(sessions[0]?.target).toEqual({ scope: 'rate_key', rateKey: 'pss' });
    expect(readPersistedSyncIds()).toEqual(['abc-123']);
  });

  it('supprime une session terminée', () => {
    writePersistedSyncSessions([
      {
        syncId: 'abc-123',
        target: { scope: 'all' },
        isMonthly: false,
      },
    ]);
    removePersistedSyncId('abc-123');
    expect(readPersistedSyncSessions()).toEqual([]);
  });
});
