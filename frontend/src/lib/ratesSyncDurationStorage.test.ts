import { describe, expect, it, beforeEach, vi } from 'vitest';

import {
  computeCompletedSyncDurationSec,
  computeJobDurationSec,
  getStoredSyncDuration,
  recordSyncDurationForKeys,
  recordSyncDurationFromStatus,
  storageKeysFromTarget,
  maxStoredSyncDurationFromStore,
  sumStoredSyncDurationForFullSync,
  sumStoredSyncDurationForTarget,
} from '@/lib/ratesSyncDurationStorage';
import type { RatesSyncStatusResponse } from '@/api/rates';

describe('ratesSyncDurationStorage', () => {
  beforeEach(() => {
    const store = new Map<string, string>();
    vi.stubGlobal('localStorage', {
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

  it('persiste et relit une durée par rate_key', () => {
    recordSyncDurationForKeys(['pss'], 92);
    expect(getStoredSyncDuration('pss')).toBe(92);
  });

  it('mappe les cibles de sync vers des clés de stockage', () => {
    expect(storageKeysFromTarget({ scope: 'rate_key', rateKey: 'smic' })).toEqual(['smic']);
    expect(storageKeysFromTarget({ scope: 'cotisation_id', cotisationId: 'csg' })).toEqual([
      'cotisation:csg',
    ]);
  });

  it('calcule la durée murale d’un lot terminé', () => {
    const status: RatesSyncStatusResponse = {
      sync_id: 'abc',
      status: 'completed',
      created_at: '2026-05-28T10:00:00.000Z',
      progress: { total: 1, completed: 1, failed: 0, running: 0, done: 1, percent: 100 },
      jobs: [
        {
          source_key: 'PSS',
          source_name: 'PSS',
          job_id: '1',
          status: 'completed',
          started_at: '2026-05-28T10:00:00.000Z',
          completed_at: '2026-05-28T10:01:30.000Z',
          rate_keys: ['pss'],
        },
      ],
    };

    expect(computeCompletedSyncDurationSec(status)).toBe(90);
  });

  it('additionne les durées stockées pour une section multi-cartes', () => {
    recordSyncDurationForKeys(['smic'], 12);
    recordSyncDurationForKeys(['pss'], 25);
    recordSyncDurationForKeys(['ij_plafonds'], 18);

    expect(
      sumStoredSyncDurationForTarget({
        scope: 'rate_keys',
        rateKeys: ['smic', 'pss', 'ij_plafonds'],
        sectionLabel: 'Paramètres clés',
      }),
    ).toBe(55);
  });

  it('estime la durée murale d’une sync complète (max parallèle ou lot global)', () => {
    recordSyncDurationForKeys(['smic'], 12);
    recordSyncDurationForKeys(['pss'], 25);
    expect(maxStoredSyncDurationFromStore()).toBe(25);
    expect(sumStoredSyncDurationForFullSync()).toBe(25);

    recordSyncDurationForKeys(['__all__'], 180);
    expect(sumStoredSyncDurationForFullSync()).toBe(180);
    expect(sumStoredSyncDurationForTarget({ scope: 'all' })).toBe(180);
  });

  it('enregistre une durée par job lors d’une sync de section', () => {
    const status: RatesSyncStatusResponse = {
      sync_id: 'section-1',
      status: 'completed',
      created_at: '2026-05-28T10:00:00.000Z',
      progress: { total: 3, completed: 3, failed: 0, running: 0, done: 3, percent: 100 },
      jobs: [
        {
          source_key: 'SMIC',
          source_name: 'SMIC',
          job_id: '1',
          status: 'completed',
          started_at: '2026-05-28T10:00:00.000Z',
          completed_at: '2026-05-28T10:00:12.000Z',
          rate_keys: ['smic'],
        },
        {
          source_key: 'PSS',
          source_name: 'PSS',
          job_id: '2',
          status: 'completed',
          started_at: '2026-05-28T10:00:00.000Z',
          completed_at: '2026-05-28T10:00:25.000Z',
          rate_keys: ['pss'],
        },
        {
          source_key: 'IJ_MALADIE',
          source_name: 'IJ',
          job_id: '3',
          status: 'completed',
          started_at: '2026-05-28T10:00:00.000Z',
          completed_at: '2026-05-28T10:00:18.000Z',
          rate_keys: ['ij_plafonds'],
        },
      ],
    };

    recordSyncDurationFromStatus(
      { scope: 'rate_keys', rateKeys: ['smic', 'pss', 'ij_plafonds'] },
      status,
    );

    expect(getStoredSyncDuration('smic')).toBe(12);
    expect(getStoredSyncDuration('pss')).toBe(25);
    expect(getStoredSyncDuration('ij_plafonds')).toBe(18);
    expect(
      sumStoredSyncDurationForTarget({
        scope: 'rate_keys',
        rateKeys: ['smic', 'pss', 'ij_plafonds'],
      }),
    ).toBe(55);
  });

  it('calcule la durée d’un job individuel', () => {
    const batchStart = Date.parse('2026-05-28T10:00:00.000Z');
    expect(
      computeJobDurationSec(
        {
          source_key: 'PSS',
          source_name: 'PSS',
          job_id: '1',
          status: 'completed',
          started_at: '2026-05-28T10:00:00.000Z',
          completed_at: '2026-05-28T10:01:30.000Z',
        },
        batchStart,
      ),
    ).toBe(90);
  });
});
