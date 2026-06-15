import { describe, expect, it } from 'vitest';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import {
  computeEmployeeRowStatus,
  computeMonthCompletionStatus,
  isDayReadyForPayroll,
} from './calendarStats';

const YEAR = 2026;
const MONTH = 6;

function planned(
  jour: number,
  type: string,
  heures_prevues: number | null = null
): PlannedEventData {
  return { jour, type, heures_prevues };
}

function actual(
  jour: number,
  type: string,
  heures_faites: number | null = null
): ActualHoursData {
  return { jour, type, heures_faites };
}

function buildFullJuneCalendar(
  weekdayTravail: (day: number) => {
    prev: number | null;
    fait: number | null;
  }
): { planned: PlannedEventData[]; actual: ActualHoursData[] } {
  const plannedDays: PlannedEventData[] = [];
  const actualDays: ActualHoursData[] = [];

  for (let day = 1; day <= 30; day++) {
    const date = new Date(YEAR, MONTH - 1, day);
    const isWeekend = date.getDay() === 0 || date.getDay() === 6;
    if (isWeekend) {
      plannedDays.push(planned(day, 'weekend', 0));
      actualDays.push(actual(day, 'weekend', 0));
      continue;
    }
    const { prev, fait } = weekdayTravail(day);
    plannedDays.push(planned(day, 'travail', prev));
    actualDays.push(actual(day, 'travail', fait));
  }

  return { planned: plannedDays, actual: actualDays };
}

describe('isDayReadyForPayroll', () => {
  it('exige prévu et réel pour un jour travail', () => {
    expect(
      isDayReadyForPayroll(planned(3, 'travail', 8), actual(3, 'travail', 8))
    ).toBe(true);
    expect(
      isDayReadyForPayroll(planned(3, 'travail', 8), actual(3, 'travail', null))
    ).toBe(false);
    expect(
      isDayReadyForPayroll(planned(3, 'travail', null), actual(3, 'travail', 8))
    ).toBe(false);
  });

  it('accepte 0 comme valeur renseignée quand aucune heure n est prévue', () => {
    expect(
      isDayReadyForPayroll(planned(3, 'travail', 0), actual(3, 'travail', 0))
    ).toBe(true);
  });

  it('considère 0 h comme non saisi quand des heures sont prévues', () => {
    expect(
      isDayReadyForPayroll(planned(3, 'travail', 8), actual(3, 'travail', 0))
    ).toBe(false);
    expect(
      isDayReadyForPayroll(planned(3, 'travail', 8), actual(3, 'travail', 0), true)
    ).toBe(true);
  });

  it('considère les jours non-travail complets sans heures', () => {
    expect(isDayReadyForPayroll(planned(7, 'weekend', 0), undefined)).toBe(true);
    expect(isDayReadyForPayroll(planned(10, 'conge', 0), undefined)).toBe(true);
    expect(isDayReadyForPayroll(planned(11, 'ferie', null), undefined)).toBe(true);
  });

  it('exige prévu et réel pour un samedi marqué travail', () => {
    expect(
      isDayReadyForPayroll(planned(6, 'travail', 8), actual(6, 'travail', null))
    ).toBe(false);
    expect(
      isDayReadyForPayroll(planned(6, 'travail', 8), actual(6, 'travail', 7))
    ).toBe(true);
  });
});

describe('computeMonthCompletionStatus', () => {
  it('retourne a_saisir si un jour travail n a pas de réel', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar((day) => ({
      prev: 8,
      fait: day === 10 ? null : 8,
    }));
    expect(computeMonthCompletionStatus(p, a, YEAR, MONTH)).toBe('a_saisir');
  });

  it('retourne saisi quand tous les jours travail ont prévu et réel', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({
      prev: 8,
      fait: 8,
    }));
    expect(computeMonthCompletionStatus(p, a, YEAR, MONTH)).toBe('saisi');
  });

  it('retourne saisi quand weekends et congés sont complets sans heures', () => {
    const plannedDays: PlannedEventData[] = [];
    const actualDays: ActualHoursData[] = [];
    for (let day = 1; day <= 31; day++) {
      const date = new Date(2026, 0, day);
      const isWeekend = date.getDay() === 0 || date.getDay() === 6;
      if (day === 15) {
        plannedDays.push(planned(day, 'conge', 0));
        actualDays.push(actual(day, 'conge', 0));
      } else if (isWeekend) {
        plannedDays.push(planned(day, 'weekend', 0));
        actualDays.push(actual(day, 'weekend', 0));
      } else {
        plannedDays.push(planned(day, 'travail', 8));
        actualDays.push(actual(day, 'travail', 8));
      }
    }
    expect(computeMonthCompletionStatus(plannedDays, actualDays, 2026, 1)).toBe(
      'saisi'
    );
  });
});

describe('computeEmployeeRowStatus', () => {
  it('retourne a_saisir si le réel manque sur un jour travail', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({
      prev: 8,
      fait: null,
    }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, false)).toBe('a_saisir');
  });

  it('retourne a_saisir si le réel est à 0 sur un jour travail prévu', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({
      prev: 8,
      fait: 0,
    }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, false)).toBe('a_saisir');
  });

  it('retourne saisi_avec_ecart quand le mois est complet mais avec écart', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar((day) => ({
      prev: 8,
      fait: day === 2 ? 28 : 8,
    }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, false)).toBe(
      'saisi_avec_ecart'
    );
  });

  it('retourne a_saisir pour forfait jour si le réel manque', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({
      prev: 1,
      fait: null,
    }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, true)).toBe('a_saisir');
  });
});
