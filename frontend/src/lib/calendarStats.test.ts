import { describe, expect, it } from 'vitest';
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import {
  aDesHeuresPointees,
  computeEmployeeRowStatus,
  computeMonthCompletionStatus,
  isDayReadyForPayroll,
  moisPrecedent,
  pointeSurLaPeriode,
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

// Même règle que le juge du serveur (`periode_a_saisir`) : un salarié qui ne
// pointe jamais n'a rien à saisir, le prévu fait foi ; un 0 h saisi un jour
// travaillé reste à saisir.
describe('salarié qui ne pointe pas', () => {
  it('aDesHeuresPointees ne compte que les heures > 0', () => {
    expect(aDesHeuresPointees([])).toBe(false);
    expect(aDesHeuresPointees([actual(1, 'travail', null), actual(2, 'travail', 0)])).toBe(
      false
    );
    expect(aDesHeuresPointees([actual(3, 'travail', 0.5)])).toBe(true);
  });

  it('pointe sur la période si le mois ou le mois précédent a des heures', () => {
    expect(pointeSurLaPeriode([actual(1, 'travail', null)], [actual(28, 'travail', 8)])).toBe(
      true
    );
    expect(pointeSurLaPeriode([actual(1, 'travail', 8)], [])).toBe(true);
    expect(pointeSurLaPeriode([actual(1, 'travail', null)], [])).toBe(false);
  });

  it('un mois précédent illisible garde la règle stricte', () => {
    expect(pointeSurLaPeriode([], null)).toBe(true);
  });

  it('le mois précédent de janvier est décembre de l année d avant', () => {
    expect(moisPrecedent(2026, 1)).toEqual({ year: 2025, month: 12 });
    expect(moisPrecedent(2026, 9)).toEqual({ year: 2026, month: 8 });
  });

  it('un jour travail sans réel est prêt quand le salarié ne pointe pas', () => {
    expect(
      isDayReadyForPayroll(planned(3, 'travail', 8), actual(3, 'travail', null), false, false)
    ).toBe(true);
    expect(
      isDayReadyForPayroll(planned(3, 'travail', 8), actual(3, 'travail', 0), false, false)
    ).toBe(false);
  });

  it('le mois est saisi et sans écart quand le salarié ne pointe pas', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({ prev: 8, fait: null }));
    expect(computeMonthCompletionStatus(p, a, YEAR, MONTH, false, false)).toBe('saisi');
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, false, false)).toBe('saisi');
  });

  it('un forfait jour qui ne pointe pas est saisi', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({ prev: 1, fait: null }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, true, false)).toBe('saisi');
  });

  it('un 0 h saisi un jour travaillé reste à saisir', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar((day) => ({
      prev: 8,
      fait: day === 10 ? 0 : null,
    }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, false, false)).toBe('a_saisir');
  });

  it('un forfait jour saisi à 0 tout le mois garde son écart', () => {
    // Le moteur paierait le prévu (aucune heure > 0) : l'écart est le seul signal.
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({ prev: 1, fait: 0 }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, true, false)).toBe('saisi_avec_ecart');
  });

  it('des week-ends à 0 ne font pas un salarié qui pointe', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({ prev: 8, fait: null }));
    expect(a.some((j) => j.type === 'weekend' && j.heures_faites === 0)).toBe(true);
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, false, false)).toBe('saisi');
  });

  it('par défaut la règle reste stricte', () => {
    const { planned: p, actual: a } = buildFullJuneCalendar(() => ({ prev: 8, fait: null }));
    expect(computeEmployeeRowStatus(p, a, YEAR, MONTH, false)).toBe('a_saisir');
  });
});

describe('joursArretCalendairesDuMois', () => {
  const arretMarion = {
    status: 'validated',
    type: 'arret_maladie',
    // 17/08 → 31/08 calendaire (week-ends compris) = 15 jours
    selected_days: Array.from({ length: 15 }, (_, i) => `2026-08-${17 + i}`),
  };

  it('compte les jours calendaires du mois, samedis et dimanches compris', async () => {
    const { joursArretCalendairesDuMois } = await import('./calendarStats');
    expect(joursArretCalendairesDuMois([arretMarion], 2026, 8)).toBe(15);
  });

  it('ignore les autres mois, les non-validées et les non-arrêts', async () => {
    const { joursArretCalendairesDuMois } = await import('./calendarStats');
    expect(joursArretCalendairesDuMois([arretMarion], 2026, 9)).toBe(0);
    expect(
      joursArretCalendairesDuMois(
        [{ ...arretMarion, status: 'pending' }],
        2026,
        8
      )
    ).toBe(0);
    expect(
      joursArretCalendairesDuMois(
        [{ ...arretMarion, type: 'conge_paye' }],
        2026,
        8
      )
    ).toBe(0);
  });

  it('ne double-compte pas des demandes chevauchantes', async () => {
    const { joursArretCalendairesDuMois } = await import('./calendarStats');
    expect(
      joursArretCalendairesDuMois([arretMarion, { ...arretMarion }], 2026, 8)
    ).toBe(15);
  });
});

describe('joursJtcDeLAnnee', () => {
  it("compte les jours JTC validés de l'année (jamais écrits au calendrier)", async () => {
    const { joursJtcDeLAnnee } = await import('./calendarStats');
    const jtc = {
      status: 'validated',
      type: 'jtc',
      selected_days: ['2026-05-04', '2026-05-05', '2025-12-31'],
    };
    expect(joursJtcDeLAnnee([jtc], 2026)).toBe(2);
    expect(joursJtcDeLAnnee([{ ...jtc, status: 'pending' }], 2026)).toBe(0);
  });
});
