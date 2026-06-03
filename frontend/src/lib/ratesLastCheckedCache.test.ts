import { describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';

import type { RatesResponse } from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';
import {
  applyCompletedSyncJobsToRatesCache,
  patchRatesLastCheckedInCache,
} from '@/lib/ratesLastCheckedCache';

describe('ratesLastCheckedCache', () => {
  it('met à jour last_checked_at sur une carte rate_key', () => {
    const queryClient = new QueryClient();
    const companyId = 'co-1';
    const data: RatesResponse = {
      smic: {
        config_data: { cas_general: 12.31 },
        version: 1,
        last_checked_at: '2026-05-01T10:00:00Z',
        comment: null,
        source_links: null,
      },
    };
    queryClient.setQueryData(queryKeys.rates(companyId), data);

    patchRatesLastCheckedInCache(queryClient, companyId, {
      rateKeys: ['smic'],
      checkedAt: '2026-06-01T14:52:00Z',
    });

    const fresh = queryClient.getQueryData<RatesResponse>(queryKeys.rates(companyId));
    expect(fresh?.smic.last_checked_at).toBe('2026-06-01T14:52:00Z');
  });

  it('met à jour last_checked_at sur une ligne de cotisation', () => {
    const queryClient = new QueryClient();
    const companyId = 'co-1';
    const data: RatesResponse = {
      cotisations: {
        config_data: {
          cotisations: [
            { id: 'csg', libelle: 'CSG', base: 'brut', last_checked_at: null },
          ],
        },
        version: 1,
        last_checked_at: null,
        comment: null,
        source_links: null,
      },
    };
    queryClient.setQueryData(queryKeys.rates(companyId), data);

    patchRatesLastCheckedInCache(queryClient, companyId, {
      cotisationIds: ['csg'],
      checkedAt: '2026-06-01T14:52:00Z',
    });

    const fresh = queryClient.getQueryData<RatesResponse>(queryKeys.rates(companyId));
    const items = (fresh?.cotisations.config_data as { cotisations: { last_checked_at?: string }[] })
      .cotisations;
    expect(items[0].last_checked_at).toBe('2026-06-01T14:52:00Z');
  });

  it('applique les jobs terminés avec succès', () => {
    const queryClient = new QueryClient();
    const companyId = 'co-1';
    queryClient.setQueryData(queryKeys.rates(companyId), {
      pss: {
        config_data: {},
        version: 1,
        last_checked_at: null,
        comment: null,
        source_links: null,
      },
    } satisfies RatesResponse);

    applyCompletedSyncJobsToRatesCache(queryClient, companyId, [
      {
        source_key: 'PSS',
        source_name: 'PSS',
        job_id: 'j1',
        status: 'completed',
        success: true,
        completed_at: '2026-06-01T15:00:00Z',
        rate_keys: ['pss'],
      },
      {
        source_key: 'SMIC',
        source_name: 'SMIC',
        job_id: 'j2',
        status: 'failed',
        success: false,
        rate_keys: ['smic'],
      },
    ]);

    const fresh = queryClient.getQueryData<RatesResponse>(queryKeys.rates(companyId));
    expect(fresh?.pss.last_checked_at).toBe('2026-06-01T15:00:00Z');
  });
});
