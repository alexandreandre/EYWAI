import { describe, expect, it } from 'vitest';
import {
  CONTINGENT_STATUS_LABELS,
  getUsageBarColor,
  matchesContingentFilter,
} from './contingentStatus';

describe('contingentStatus', () => {
  it('labels all statuses', () => {
    expect(CONTINGENT_STATUS_LABELS.ok).toBeTruthy();
    expect(CONTINGENT_STATUS_LABELS.cor_exceeded).toContain('COR');
  });

  it('usage bar color thresholds', () => {
    expect(getUsageBarColor(50)).toBe('bg-emerald-500');
    expect(getUsageBarColor(85)).toBe('bg-amber-500');
    expect(getUsageBarColor(100)).toBe('bg-destructive');
  });

  it('filter matches status', () => {
    expect(matchesContingentFilter('near_limit', 'near_limit')).toBe(true);
    expect(matchesContingentFilter('ok', 'near_limit')).toBe(false);
    expect(matchesContingentFilter('ok', 'all')).toBe(true);
  });
});
