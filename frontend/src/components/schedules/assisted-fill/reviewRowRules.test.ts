import { describe, expect, it } from 'vitest';
import {
  reservedEmployeeIds,
  rowCarriesHours,
  statusAfterLosingEmployee,
  visibleRowWarnings,
} from './reviewRowRules';

const travail = (heures: number | null) => ({ heures, type: 'travail' });

describe('rowCarriesHours', () => {
  it('une ligne avec une heure travaillée porte quelque chose', () => {
    expect(rowCarriesHours({ employeeId: 'e1', days: [travail(7.5)] })).toBe(true);
  });

  it('un jour d’absence porte une information même à 0 h', () => {
    expect(
      rowCarriesHours({ employeeId: 'e1', days: [{ heures: 0, type: 'conge' }] }),
    ).toBe(true);
  });

  it('une semaine vide ou à 0 h ne porte rien', () => {
    expect(rowCarriesHours({ employeeId: 'e1', days: [] })).toBe(false);
    expect(rowCarriesHours({ employeeId: 'e1', days: [travail(0), travail(null)] })).toBe(false);
  });
});

describe('reservedEmployeeIds', () => {
  it('une ligne vide ne réserve pas son salarié : on peut l’associer à la ligne qui porte ses heures', () => {
    const rows = [
      { employeeId: 'm1', days: [] },
      { employeeId: 'b1', days: [travail(8)] },
      { employeeId: null, days: [travail(9)] },
    ];
    expect(reservedEmployeeIds(rows)).toEqual(['b1']);
  });
});

describe('statusAfterLosingEmployee', () => {
  it('une ligne vide qui perd son salarié reste « Semaine vide »', () => {
    expect(statusAfterLosingEmployee({ employeeId: 'm1', days: [] })).toBe('empty');
  });

  it('une ligne avec des heures qui perd son salarié attend une association', () => {
    expect(statusAfterLosingEmployee({ employeeId: 'm1', days: [travail(8)] })).toBe('error');
  });
});

describe('visibleRowWarnings', () => {
  it('montre tous les avertissements d’une ligne à vérifier, pas seulement le premier', () => {
    const warnings = [
      'Nom seul « DUPRAT » rapproché de Claire MOREL (nom d’usage) : seul salarié de ce nom.',
      'Relevé à relire — Martine a retenu les heures du badge, pas les annotations : ven 18/09 « +1 ».',
    ];
    expect(visibleRowWarnings(warnings, 'warning')).toEqual(warnings);
  });

  it('ne montre rien sous une ligne prête', () => {
    expect(visibleRowWarnings(['bruit'], 'ok')).toEqual([]);
  });
});
