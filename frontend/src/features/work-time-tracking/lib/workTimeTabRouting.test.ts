import { describe, expect, it } from 'vitest';
import {
  DEFAULT_WORK_TIME_TAB,
  parseWorkTimeTab,
  workTimeHubPath,
} from './workTimeTabRouting';

describe('workTimeTabRouting', () => {
  it('parseWorkTimeTab returns default for invalid values', () => {
    expect(parseWorkTimeTab(null)).toBe(DEFAULT_WORK_TIME_TAB);
    expect(parseWorkTimeTab(undefined)).toBe(DEFAULT_WORK_TIME_TAB);
    expect(parseWorkTimeTab('invalid')).toBe(DEFAULT_WORK_TIME_TAB);
  });

  it('parseWorkTimeTab accepts valid tabs', () => {
    expect(parseWorkTimeTab('contingent')).toBe('contingent');
    expect(parseWorkTimeTab('compte-heures')).toBe('compte-heures');
  });

  it('workTimeHubPath builds canonical and query URLs', () => {
    expect(workTimeHubPath()).toBe('/suivi-temps-travail');
    expect(workTimeHubPath({ tab: 'compte-heures' })).toBe(
      '/suivi-temps-travail?tab=compte-heures',
    );
    expect(workTimeHubPath({ tab: 'contingent', employee: 'emp-1' })).toBe(
      '/suivi-temps-travail?employee=emp-1',
    );
    expect(workTimeHubPath({ tab: 'compte-heures', employee: 'emp-1' })).toBe(
      '/suivi-temps-travail?tab=compte-heures&employee=emp-1',
    );
  });
});
