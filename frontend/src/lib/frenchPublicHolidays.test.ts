import { describe, expect, it } from 'vitest';
import {
  FRENCH_PUBLIC_HOLIDAY_IDS,
  getDefaultObservedHolidayIds,
  getHolidayInstances,
  getObservedHolidayDayNumbers,
  normalizeObservedHolidayIds,
} from '@/lib/frenchPublicHolidays';

describe('frenchPublicHolidays', () => {
  it('returns all 11 holidays by default', () => {
    expect(getDefaultObservedHolidayIds()).toHaveLength(11);
    expect(FRENCH_PUBLIC_HOLIDAY_IDS).toHaveLength(11);
  });

  it('always keeps labor day when filtering observed ids', () => {
    const ids = normalizeObservedHolidayIds(['christmas']);
    expect(ids).toContain('labor_day');
    expect(ids).toContain('christmas');
    expect(ids).not.toContain('whit_monday');
  });

  it('excludes whit monday from observed day numbers when unchecked', () => {
    const year = 2026;
    const month = 5;
    const all = getObservedHolidayDayNumbers(year, month);
    const withoutWhit = getObservedHolidayDayNumbers(year, month, [
      ...FRENCH_PUBLIC_HOLIDAY_IDS.filter((id) => id !== 'whit_monday'),
    ]);

    const whit = getHolidayInstances(year).find((h) => h.id === 'whit_monday');
    expect(whit?.month).toBe(5);
    expect(all.has(whit!.day)).toBe(true);
    expect(withoutWhit.has(whit!.day)).toBe(false);
    expect(withoutWhit.has(1)).toBe(true);
  });
});
