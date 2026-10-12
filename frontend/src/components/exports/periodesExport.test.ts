import { describe, expect, it } from 'vitest';

import { anneesProposees, optionsDeMois } from './periodesExport';

const OCTOBRE_2026 = new Date(2026, 9, 12);

describe('optionsDeMois', () => {
  it('sans année choisie : les 12 mois d’avant, le mois en cours et les 2 suivants', () => {
    const options = optionsDeMois(OCTOBRE_2026, null);
    expect(options).toHaveLength(15);
    expect(options[0]).toEqual({ value: '2025-10', label: 'Octobre 2025' });
    expect(options[12].value).toBe('2026-10');
    expect(options[14].value).toBe('2026-12');
  });

  it('avec une année choisie : ses douze mois, même plus anciens que 12 mois', () => {
    const options = optionsDeMois(OCTOBRE_2026, 2024);
    expect(options.map((o) => o.value)).toEqual([
      '2024-01',
      '2024-02',
      '2024-03',
      '2024-04',
      '2024-05',
      '2024-06',
      '2024-07',
      '2024-08',
      '2024-09',
      '2024-10',
      '2024-11',
      '2024-12',
    ]);
    expect(options[0].label).toBe('Janvier 2024');
  });
});

describe('anneesProposees', () => {
  it('remonte de l’année en cours à six ans en arrière', () => {
    expect(anneesProposees(OCTOBRE_2026)).toEqual([2026, 2025, 2024, 2023, 2022, 2021, 2020]);
  });
});
