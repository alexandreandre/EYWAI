import { describe, expect, it } from 'vitest';
import {
  computePlanningWeeks,
  defaultPlanningWeekIndex,
  planningWeekDays,
  planningWeekLabel,
} from './planningWeeks';

describe('computePlanningWeeks', () => {
  it('découpe août 2026 en semaines lundi–dimanche, comme la vue planning', () => {
    const weeks = computePlanningWeeks(2026, 8);
    expect(weeks[0]).toEqual([0, 0, 0, 0, 0, 1, 2]);
    expect(weeks[1]).toEqual([3, 4, 5, 6, 7, 8, 9]);
    expect(weeks[weeks.length - 1][0]).toBe(31);
    expect(planningWeekLabel(weeks[1])).toBe('3–9');
    expect(planningWeekDays(weeks[0])).toEqual([1, 2]);
  });

  it('sélectionne la semaine du jour en cours quand on est dans le mois', () => {
    const today = new Date(2026, 7, 5);
    expect(defaultPlanningWeekIndex(2026, 8, today)).toBe(1);
  });

  it('revient à la première semaine si le jour n’est pas dans le mois', () => {
    const today = new Date(2026, 0, 15);
    expect(defaultPlanningWeekIndex(2026, 8, today)).toBe(0);
  });
});
