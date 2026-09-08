import { describe, expect, it } from 'vitest';

import {
  filterEmployeesForMonth,
  filterPresentEmployees,
  isPresentDuringMonth,
  isPresentEmployee,
} from './employmentStatus';

describe('isPresentEmployee', () => {
  it('garde les salariés en poste', () => {
    expect(isPresentEmployee('actif')).toBe(true);
    expect(isPresentEmployee('active')).toBe(true);
    expect(isPresentEmployee('en_onboarding')).toBe(true);
    expect(isPresentEmployee('en_sortie')).toBe(true);
    expect(isPresentEmployee(undefined)).toBe(true);
    expect(isPresentEmployee(null)).toBe(true);
  });

  it('exclut les salariés partis', () => {
    expect(isPresentEmployee('parti')).toBe(false);
    expect(isPresentEmployee('inactif')).toBe(false);
    expect(isPresentEmployee('sorti')).toBe(false);
  });
});

describe('filterPresentEmployees', () => {
  it('retire les partis de la liste calendrier', () => {
    const kept = filterPresentEmployees([
      { id: '1', employment_status: 'actif' },
      { id: '2', employment_status: 'parti' },
      { id: '3', employment_status: 'en_onboarding' },
      { id: '4', employment_status: 'inactif' },
    ]);
    expect(kept.map((e) => e.id)).toEqual(['1', '3']);
  });
});

describe('isPresentDuringMonth', () => {
  const demory = {
    employment_status: 'parti',
    exit_last_working_day: '2026-07-24',
  };

  it('garde un parti sur les mois où il était présent (Demory, sorti le 24/07)', () => {
    expect(isPresentDuringMonth(demory, 2026, 7)).toBe(true);
    expect(isPresentDuringMonth(demory, 2026, 6)).toBe(true);
  });

  it('le retire des mois postérieurs à son départ', () => {
    expect(isPresentDuringMonth(demory, 2026, 8)).toBe(false);
    expect(isPresentDuringMonth(demory, 2027, 1)).toBe(false);
  });

  it('sans date de sortie connue, un parti reste exclu', () => {
    expect(
      isPresentDuringMonth({ employment_status: 'parti' }, 2026, 7),
    ).toBe(false);
  });

  it('un salarié en poste est visible sur tous les mois', () => {
    expect(
      isPresentDuringMonth({ employment_status: 'actif' }, 2027, 3),
    ).toBe(true);
  });
});

describe('filterEmployeesForMonth', () => {
  it('combine présents et partis du mois affiché', () => {
    const kept = filterEmployeesForMonth(
      [
        { id: '1', employment_status: 'actif' },
        {
          id: '2',
          employment_status: 'parti',
          exit_last_working_day: '2026-07-24',
        },
        {
          id: '3',
          employment_status: 'parti',
          exit_last_working_day: '2026-05-02',
        },
      ],
      2026,
      7,
    );
    expect(kept.map((e) => e.id)).toEqual(['1', '2']);
  });
});
