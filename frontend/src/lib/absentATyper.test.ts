import { describe, expect, it } from 'vitest';
import {
  TYPE_ABSENT_A_TYPER,
  estAbsentATyper,
  joursAbsentsATyper,
  phraseAbsentsATyper,
} from './absentATyper';
import { computeGlobalKpis, type EmployeeCalendarOverviewRow } from './schedulesOverview';

describe('jours « absent, type à donner »', () => {
  it('repère les jours du prévu marqués absents', () => {
    const prevu = [
      { jour: 8, type: 'travail', heures_prevues: 7 },
      { jour: 9, type: TYPE_ABSENT_A_TYPER, heures_prevues: 7 },
      { jour: 10, type: 'conges_payes', heures_prevues: 0 },
      { jour: 11, type: TYPE_ABSENT_A_TYPER, heures_prevues: 7 },
    ];
    expect(joursAbsentsATyper(prevu)).toEqual([9, 11]);
    expect(estAbsentATyper(prevu[1])).toBe(true);
    expect(estAbsentATyper(prevu[2])).toBe(false);
  });

  it('dit les jours en clair', () => {
    expect(phraseAbsentsATyper([9])).toBe('1 jour absent sans type (le 9)');
    expect(phraseAbsentsATyper([9, 11])).toBe('2 jours absents sans type (les 9 et 11)');
  });

  it('un salarié avec un jour absent sans type n’est pas prêt pour la paie', () => {
    const ligne = {
      employee: { id: 'e1' },
      planned: [],
      actual: [],
      heuresPrevues: 0,
      heuresFaites: 0,
      ecart: 0,
      rowStatus: 'saisi',
      absenceConflictDays: [],
      joursAbsentsATyper: [9],
      loadError: false,
      isForfaitJour: false,
    } as unknown as EmployeeCalendarOverviewRow;
    const kpis = computeGlobalKpis([ligne]);
    expect(kpis.prets).toBe(0);
    expect(kpis.avecAbsentsATyper).toBe(1);
  });
});
