import { describe, expect, it } from 'vitest';
import {
  buildActualEntriesFromWeekConfig,
  buildPlannedEntriesFromWeekConfig,
  weekNumberForMonthDay,
  type ApplyModelWeekConfig,
} from './applyWeekModel';
import { computePlanningWeeks, planningWeekDays } from './planningWeeks';

const work = { type: 'travail' as const, hours: 7 };
const weekend = { type: 'weekend' as const, hours: 0 };
const week: ApplyModelWeekConfig = {
  monday: work,
  tuesday: work,
  wednesday: work,
  thursday: work,
  friday: work,
  saturday: weekend,
  sunday: weekend,
};

describe('weekNumberForMonthDay', () => {
  it('aligne août 2026 sur la même numérotation que apply-model serveur', () => {
    expect(weekNumberForMonthDay(2026, 8, 1)).toBe(1);
    expect(weekNumberForMonthDay(2026, 8, 2)).toBe(1);
    expect(weekNumberForMonthDay(2026, 8, 3)).toBe(2);
    expect(weekNumberForMonthDay(2026, 8, 31)).toBe(5);
  });
});

describe('buildActualEntriesFromWeekConfig', () => {
  it('pose les heures faites du lundi au vendredi, 0 le week-end', () => {
    const days = buildActualEntriesFromWeekConfig(2026, 8, week, false);
    expect(days.find((d) => d.jour === 3)).toEqual({
      jour: 3,
      type: 'travail',
      heures_faites: 7,
    });
    expect(days.find((d) => d.jour === 1)).toEqual({
      jour: 1,
      type: 'weekend',
      heures_faites: 0,
    });
    expect(days.find((d) => d.jour === 31)).toEqual({
      jour: 31,
      type: 'travail',
      heures_faites: 7,
    });
    expect(days).toHaveLength(31);
  });

  it('normalise le forfait jour en 1 / 0', () => {
    const days = buildActualEntriesFromWeekConfig(2026, 8, week, true);
    expect(days.find((d) => d.jour === 3)?.heures_faites).toBe(1);
    expect(days.find((d) => d.jour === 1)?.heures_faites).toBe(0);
  });

  it('pose 0 heure sur un jour non travaillé même si le champ heures est remplis', () => {
    const congeWeek: ApplyModelWeekConfig = {
      ...week,
      monday: { type: 'conge', hours: 8 },
    };
    const days = buildActualEntriesFromWeekConfig(2026, 8, congeWeek, false);
    expect(days.find((d) => d.jour === 3)).toEqual({
      jour: 3,
      type: 'conge',
      heures_faites: 0,
    });
  });

  it('conserve les jours d’absence validée déjà saisis', () => {
    const existing = [{ jour: 3, type: 'arret_maladie', heures_faites: 0 }];
    const planned = [
      { jour: 3, type: 'arret_maladie', heures_prevues: 0, origine: 'absence' },
    ];
    const days = buildActualEntriesFromWeekConfig(2026, 8, week, false, {
      existing,
      planned,
    });
    expect(days.find((d) => d.jour === 3)).toEqual({
      jour: 3,
      type: 'arret_maladie',
      heures_faites: 0,
    });
  });

  it('n’écrit que la semaine demandée et conserve le reste du mois', () => {
    const weekDays = planningWeekDays(computePlanningWeeks(2026, 8)[1]);
    const existing = [
      { jour: 1, type: 'weekend', heures_faites: 4 },
      { jour: 10, type: 'travail', heures_faites: 9 },
    ];
    const days = buildActualEntriesFromWeekConfig(2026, 8, week, false, {
      existing,
      onlyDays: weekDays,
    });
    expect(weekDays).toEqual([3, 4, 5, 6, 7, 8, 9]);
    expect(days.find((d) => d.jour === 1)?.heures_faites).toBe(4);
    expect(days.find((d) => d.jour === 3)?.heures_faites).toBe(7);
    expect(days.find((d) => d.jour === 10)?.heures_faites).toBe(9);
  });
});

describe('buildPlannedEntriesFromWeekConfig', () => {
  it('n’écrit que la semaine demandée sur le prévu', () => {
    const weekDays = planningWeekDays(computePlanningWeeks(2026, 8)[1]);
    const existing = [
      { jour: 1, type: 'weekend', heures_prevues: 0 },
      { jour: 10, type: 'travail', heures_prevues: 8 },
    ];
    const days = buildPlannedEntriesFromWeekConfig(2026, 8, week, false, {
      existing,
      onlyDays: weekDays,
    });
    expect(days.find((d) => d.jour === 1)?.heures_prevues).toBe(0);
    expect(days.find((d) => d.jour === 3)).toEqual({
      jour: 3,
      type: 'travail',
      heures_prevues: 7,
    });
    expect(days.find((d) => d.jour === 10)?.heures_prevues).toBe(8);
  });
});
