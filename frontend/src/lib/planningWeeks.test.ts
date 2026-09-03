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

describe('planningWeekIsoNumber', () => {
  it('donne les vrais numéros ISO des semaines du mois', async () => {
    const { computePlanningWeeks, planningWeekIsoNumber } = await import(
      './planningWeeks'
    );
    // Août 2026 : le sam. 1er août est en S31 ; la semaine du 3 au 9 est S32.
    const weeks = computePlanningWeeks(2026, 8);
    expect(planningWeekIsoNumber(2026, 8, weeks[0])).toBe(31);
    expect(planningWeekIsoNumber(2026, 8, weeks[1])).toBe(32);
  });

  it('gère la bascule d’année ISO (janvier)', async () => {
    const { computePlanningWeeks, planningWeekIsoNumber } = await import(
      './planningWeeks'
    );
    // Jeudi 1er janvier 2026 → S1 ; la semaine suivante (5–11) → S2.
    const weeks = computePlanningWeeks(2026, 1);
    expect(planningWeekIsoNumber(2026, 1, weeks[0])).toBe(1);
    expect(planningWeekIsoNumber(2026, 1, weeks[1])).toBe(2);
  });

  it('rend null pour une semaine vide', async () => {
    const { planningWeekIsoNumber } = await import('./planningWeeks');
    expect(planningWeekIsoNumber(2026, 8, [0, 0, 0, 0, 0, 0, 0])).toBe(null);
  });
});
