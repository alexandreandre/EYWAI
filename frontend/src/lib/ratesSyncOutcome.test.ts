import { describe, expect, it } from 'vitest';

import type { RatesSyncStatusResponse } from '@/api/rates';
import {
  buildSyncOutcomePresentation,
  humanizeSyncError,
} from '@/lib/ratesSyncOutcome';

describe('humanizeSyncError', () => {
  it('retourne un message par défaut si vide', () => {
    expect(humanizeSyncError(null)).toMatch(/erreur est survenue/);
  });

  it('humanise les erreurs techniques', () => {
    expect(humanizeSyncError('Script non trouvé : /foo/bar.py')).toMatch(/support/);
    expect(humanizeSyncError('[ERREUR] Connexion refusée')).toBe('Connexion refusée');
  });
});

describe('buildSyncOutcomePresentation', () => {
  const base: RatesSyncStatusResponse = {
    sync_id: 'x',
    status: 'failed',
    progress: {
      total: 1,
      completed: 0,
      failed: 1,
      running: 0,
      done: 1,
      percent: 100,
    },
    jobs: [
      {
        source_key: 'pss',
        source_name: 'PSS',
        job_id: 'j1',
        status: 'failed',
        error_message: 'Le traitement s\'est interrompu',
        execution_logs: ['Démarrage — PSS', '[ERREUR] timeout'],
      },
    ],
    created_at: '2025-01-01T00:00:00Z',
  };

  it('signale un échec total', () => {
    const p = buildSyncOutcomePresentation(base);
    expect(p.tone).toBe('error');
    expect(p.failedJobs).toHaveLength(1);
    expect(p.jobsWithLogs).toHaveLength(1);
  });

  it('signale une mise à jour partielle', () => {
    const partial: RatesSyncStatusResponse = {
      ...base,
      status: 'completed_with_errors',
      jobs: [
        ...base.jobs,
        {
          source_key: 'smic',
          source_name: 'SMIC',
          job_id: 'j2',
          status: 'completed',
          success: true,
        },
      ],
    };
    const p = buildSyncOutcomePresentation(partial);
    expect(p.tone).toBe('warning');
    expect(p.failedJobs).toHaveLength(1);
  });

  it('résume une section multi-clés', () => {
    const section: RatesSyncStatusResponse = {
      sync_id: 'batch',
      status: 'completed',
      progress: {
        total: 3,
        completed: 3,
        failed: 0,
        running: 0,
        done: 3,
        percent: 100,
      },
      jobs: [],
      created_at: '2025-01-01T00:00:00Z',
      target: { rate_keys: ['smic', 'pss', 'ij_plafonds'] },
    };
    const p = buildSyncOutcomePresentation(section);
    expect(p.title).toBe('Section mise à jour');
    expect(p.summary).toContain('SMIC');
    expect(p.summary).toContain('PSS');
    expect(p.summary).toContain('Plafonds IJSS');
  });
});
