import { describe, expect, it } from 'vitest';
import { QueryClient } from '@tanstack/react-query';

import type { DsnCoverageAdminMatrixResponse } from '@/api/dsnImport';
import {
  expandPeriodRange,
  extractCommittedCoverageFromBatch,
  patchDsnCoverageMatrixCache,
} from '@/lib/dsnCoverageCache';

describe('dsnCoverageCache', () => {
  it('déploie une plage de périodes inclusive', () => {
    expect(expandPeriodRange('2026-01', '2026-03')).toEqual([
      '2026-01',
      '2026-02',
      '2026-03',
    ]);
    expect(expandPeriodRange('2026-12', '2027-02')).toEqual([
      '2026-12',
      '2027-01',
      '2027-02',
    ]);
  });

  it('extrait entreprise et périodes depuis un batch commité', () => {
    const result = extractCommittedCoverageFromBatch({
      batch: {
        id: 'b1',
        uploaded_by: 'u1',
        file_names: ['a.dsn'],
        status: 'committed',
        summary: {},
        period_min: '2026-02',
        period_max: '2026-02',
      },
      summary: {
        target_company_id: 'co-1',
        periods_committed: ['2026-02'],
      },
    });
    expect(result).toEqual({ companyId: 'co-1', periods: ['2026-02'] });
  });

  it('passe les cases concernées en vert dans le cache matrice', () => {
    const queryClient = new QueryClient();
    const matrix: DsnCoverageAdminMatrixResponse = {
      year: 2026,
      companies: [
        {
          company_id: 'co-1',
          company_name: 'Alpha',
          dsn_sync_mode: 'external',
          status: 'missing',
          expected_last_period: '2026-03',
          gaps_count: 2,
          months_covered: ['2026-01'],
          timeline: [
            { period: '2026-01', month: 1, state: 'covered' },
            { period: '2026-02', month: 2, state: 'missing' },
            { period: '2026-03', month: 3, state: 'missing' },
            { period: '2026-04', month: 4, state: 'future' },
          ],
        },
      ],
    };
    queryClient.setQueryData(['dsn-admin-matrix', 2026], matrix);

    patchDsnCoverageMatrixCache(queryClient, {
      companyId: 'co-1',
      periods: ['2026-02'],
    });

    const fresh = queryClient.getQueryData<DsnCoverageAdminMatrixResponse>([
      'dsn-admin-matrix',
      2026,
    ]);
    const company = fresh?.companies[0];
    expect(company?.timeline[1].state).toBe('covered');
    expect(company?.months_covered).toContain('2026-02');
    expect(company?.timeline[3].state).toBe('future');
  });
});
