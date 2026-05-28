import { describe, expect, it } from 'vitest';

import { buildRatesSnapshot, countChangedCategories } from '@/lib/ratesUtils';
import { currentMonthKey } from '@/lib/ratesMonthlyAuto';
import type { RatesResponse } from '@/api/rates';

describe('ratesUtils', () => {
  it('detects version and date changes', () => {
    const before = buildRatesSnapshot({
      smic: {
        config_data: {},
        version: 1,
        last_checked_at: '2025-01-01T00:00:00Z',
        comment: null,
        source_links: null,
      },
    });
    const after: RatesResponse = {
      smic: {
        config_data: {},
        version: 2,
        last_checked_at: '2025-02-01T00:00:00Z',
        comment: null,
        source_links: null,
      },
    };
    expect(countChangedCategories(before, after)).toEqual(['smic']);
  });

  it('currentMonthKey returns YYYY-MM', () => {
    expect(currentMonthKey()).toMatch(/^\d{4}-\d{2}$/);
  });
});
