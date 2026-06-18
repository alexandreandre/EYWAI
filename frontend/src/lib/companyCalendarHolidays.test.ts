import { describe, expect, it } from 'vitest';
import {
  applyHolidayHints,
  shouldShowHolidayHint,
} from '@/lib/companyCalendarHolidays';
import type { PlannedEventData } from '@/api/calendar';

describe('companyCalendarHolidays', () => {
  it('applyHolidayHints respects persisted apiDay over holiday hint', () => {
    const base: PlannedEventData[] = [{ jour: 25, type: 'travail', heures_prevues: 7 }];
    const api: PlannedEventData[] = [{ jour: 25, type: 'travail', heures_prevues: 7 }];
    const result = applyHolidayHints(base, api, 2025, 12, ['christmas']);
    expect(result[0].type).toBe('travail');
  });

  it('applyHolidayHints sets ferie on empty christmas when observed', () => {
    const base: PlannedEventData[] = [{ jour: 25, type: 'travail', heures_prevues: 7 }];
    const result = applyHolidayHints(base, [], 2025, 12, ['christmas']);
    expect(result[0].type).toBe('ferie');
    expect(result[0].heures_prevues).toBeNull();
  });

  it('shouldShowHolidayHint only when type is ferie', () => {
    expect(shouldShowHolidayHint(2025, 12, 25, 'travail', ['christmas'])).toBe(false);
    expect(shouldShowHolidayHint(2025, 12, 25, 'ferie', ['christmas'])).toBe(true);
    expect(shouldShowHolidayHint(2025, 12, 25, 'ferie', ['labor_day'])).toBe(false);
  });
});
