import { describe, expect, it } from 'vitest';

import {
  collectSyncRateTargets,
  computeActiveSyncElapsedSec,
  computeSyncProgressFromJobs,
  computeTimeBasedSyncPercent,
  displaySyncProgressPercent,
  formatSyncDuration,
  formatSyncProgressEstimate,
  formatSyncProgressEstimateFromJobs,
  partitionSyncRateTargets,
  resolveJobDisplayLabel,
  shouldPartitionSyncTargets,
} from '@/lib/ratesSyncProgress';

describe('formatSyncDuration', () => {
  it('formate les secondes courtes', () => {
    expect(formatSyncDuration(45)).toBe('45 s');
  });

  it('formate les minutes', () => {
    expect(formatSyncDuration(60)).toBe('1 min');
    expect(formatSyncDuration(92)).toBe('1 min 32 s');
    expect(formatSyncDuration(120)).toBe('2 min');
  });
});

describe('formatSyncProgressEstimate', () => {
  it('n’affiche rien sans référence enregistrée', () => {
    expect(formatSyncProgressEstimate(75, null)).toBeNull();
  });

  it('estime le temps restant au démarrage à partir de la durée enregistrée', () => {
    expect(formatSyncProgressEstimate(0, 120)).toBe('Environ 2 min restantes');
    expect(formatSyncProgressEstimate(1, 55)).toBe('Environ 55 s restantes');
  });

  it('affiche le temps restant dérivé de la durée enregistrée', () => {
    expect(formatSyncProgressEstimate(75, 120)).toBe('Environ 45 s restantes');
  });

  it('indique la finalisation quand le délai habituel est dépassé', () => {
    expect(formatSyncProgressEstimate(130, 120)).toBe('Finalisation…');
  });

  it('retourne null sans données', () => {
    expect(formatSyncProgressEstimate(0, null)).toBeNull();
  });
});

describe('resolveJobDisplayLabel', () => {
  it('distingue les sources d’une sync complète de cotisations', () => {
    expect(
      resolveJobDisplayLabel({
        source_key: 'AGIRC-ARRCO',
        source_name: 'Retraite complémentaire',
        status: 'pending',
        rate_keys: ['cotisations'],
      }),
    ).toBe('Retraite complémentaire');
    expect(
      resolveJobDisplayLabel({
        source_key: 'CSG',
        source_name: 'CSG',
        status: 'pending',
        rate_keys: ['cotisations'],
      }),
    ).toBe('CSG');
  });
});

describe('shouldPartitionSyncTargets', () => {
  it('active le mode Restants / Traités pour une sync complète', () => {
    expect(shouldPartitionSyncTargets(1, 1, ['all'])).toBe(true);
    expect(shouldPartitionSyncTargets(3, 3, ['rate_keys'])).toBe(true);
    expect(shouldPartitionSyncTargets(1, 1, ['rate_key'])).toBe(false);
  });
});

describe('collectSyncRateTargets', () => {
  it('produit un chip par job en sync complète', () => {
    const targets = collectSyncRateTargets([
      {
        sync_id: 'full',
        status: 'running',
        progress: { total: 3, completed: 0, failed: 0, running: 3, done: 0, percent: 0 },
        jobs: [
          {
            source_key: 'SMIC',
            source_name: 'SMIC',
            status: 'running',
            rate_keys: ['smic'],
          },
          {
            source_key: 'AGIRC-ARRCO',
            source_name: 'Retraite complémentaire',
            status: 'pending',
            rate_keys: ['cotisations'],
          },
          {
            source_key: 'CSG',
            source_name: 'CSG',
            status: 'pending',
            rate_keys: ['cotisations'],
          },
        ],
        created_at: '2025-01-01T00:00:00Z',
      },
    ]);

    expect(targets).toHaveLength(3);
    expect(targets.map((t) => t.label)).toEqual(
      expect.arrayContaining(['SMIC', 'Retraite complémentaire', 'CSG']),
    );
  });
});

describe('partitionSyncRateTargets', () => {
  it('sépare restants, traités et échecs', () => {
    const groups = partitionSyncRateTargets([
      {
        sync_id: 'x',
        status: 'running',
        progress: { total: 3, completed: 1, failed: 1, running: 1, done: 2, percent: 50 },
        jobs: [
          {
            source_key: 'smic',
            source_name: 'SMIC',
            status: 'completed',
            success: true,
            rate_keys: ['smic'],
          },
          {
            source_key: 'pss',
            source_name: 'PSS',
            status: 'failed',
            success: false,
            rate_keys: ['pss'],
          },
          {
            source_key: 'ij',
            source_name: 'IJ',
            status: 'running',
            rate_keys: ['ij_plafonds'],
          },
        ],
        created_at: '2025-01-01T00:00:00Z',
      },
    ]);

    expect(groups.remaining).toHaveLength(1);
    expect(groups.remaining[0].label).toMatch(/IJ/i);
    expect(groups.completed).toHaveLength(1);
    expect(groups.completed[0].label).toBe('SMIC');
    expect(groups.failed).toHaveLength(1);
    expect(groups.failed[0].label).toMatch(/PSS/i);
  });
});

describe('computeTimeBasedSyncPercent', () => {
  it('progresse linéairement selon la durée de référence', () => {
    expect(computeTimeBasedSyncPercent(0, 120)).toBe(8);
    expect(computeTimeBasedSyncPercent(60, 120)).toBe(46);
    expect(computeTimeBasedSyncPercent(120, 120)).toBe(92);
  });

  it('passe à 100 % quand tous les jobs sont terminés', () => {
    expect(computeTimeBasedSyncPercent(30, 120, { allJobsDone: true })).toBe(100);
  });
});

describe('computeSyncProgressFromJobs', () => {
  it('pondère la progression par durée attendue de chaque job', () => {
    const result = computeSyncProgressFromJobs([
      {
        source_key: 'fast',
        source_name: 'Rapide',
        status: 'completed',
        progress_fraction: 1,
      },
      {
        source_key: 'slow',
        source_name: 'Lent',
        status: 'running',
        progress_fraction: 0.5,
      },
    ]);

    expect(result.percent).toBeGreaterThan(50);
    expect(result.percent).toBeLessThan(90);
    expect(result.remainingSec).not.toBeNull();
    expect(result.allDone).toBe(false);
  });

  it('passe à 100 % quand tous les jobs sont terminés', () => {
    const result = computeSyncProgressFromJobs([
      { source_key: 'a', source_name: 'A', status: 'completed' },
      { source_key: 'b', source_name: 'B', status: 'failed' },
    ]);
    expect(result.percent).toBe(100);
    expect(result.allDone).toBe(true);
  });
});

describe('formatSyncProgressEstimateFromJobs', () => {
  it('affiche uniquement le temps restant estimé', () => {
    const line = formatSyncProgressEstimateFromJobs(
      [
        { source_key: 'smic', source_name: 'SMIC', status: 'running', progress_fraction: 0.5 },
      ],
      30,
    );
    expect(line).toMatch(/restantes|Finalisation/);
    expect(line).not.toMatch(/Durée/i);
  });
});

describe('displaySyncProgressPercent', () => {
  const agg = {
    percent: 5,
    totalJobs: 2,
    doneJobs: 1,
    runningJobs: 1,
    pendingJobs: 0,
    failedJobs: 0,
    etaSeconds: null,
  };

  it('utilise la progression pondérée par job quand la liste est disponible', () => {
    expect(
      displaySyncProgressPercent(agg, true, {
        elapsedSec: 10,
        jobs: [
          { source_key: 'a', source_name: 'A', status: 'completed' },
          { source_key: 'b', source_name: 'B', status: 'running', progress_fraction: 0.5 },
        ],
      }),
    ).toBeGreaterThanOrEqual(50);
  });

  it('retombe sur la progression temporelle sans jobs', () => {
    expect(
      displaySyncProgressPercent(agg, true, { elapsedSec: 60, referenceSec: 120 }),
    ).toBe(46);
  });
});

describe('computeActiveSyncElapsedSec', () => {
  it('prend le lot le plus ancien', () => {
    const now = Date.now();
    const elapsed = computeActiveSyncElapsedSec([
      { created_at: new Date(now - 65_000).toISOString() },
      { created_at: new Date(now - 30_000).toISOString() },
    ]);
    expect(elapsed).toBeGreaterThanOrEqual(64);
    expect(elapsed).toBeLessThanOrEqual(66);
  });
});
