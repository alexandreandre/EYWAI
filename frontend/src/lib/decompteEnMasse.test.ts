import { describe, expect, it } from 'vitest';
import type { DecompteEnMasse } from '@/api/activitePartielleEnMasse';
import { detailDuSalarie, lignesDesRaisons, phraseDuDecompte } from './decompteEnMasse';

function decompte(partiel: Partial<DecompteEnMasse>): DecompteEnMasse {
  return {
    enregistre: false,
    dates: [],
    total_passes: 0,
    total_laisses: 0,
    laisses_par_raison: {},
    libelles_raisons: {},
    salaries: [],
    avertissement: null,
    ...partiel,
  };
}

describe('phraseDuDecompte', () => {
  it('aperçu : ce qui passera et ce qui restera', () => {
    expect(phraseDuDecompte(decompte({ total_passes: 12, total_laisses: 3 }))).toBe(
      '12 jours passeront en activité partielle, 3 jours resteront tels quels.',
    );
    expect(phraseDuDecompte(decompte({ total_passes: 1, total_laisses: 0 }))).toBe(
      '1 jour passera en activité partielle.',
    );
  });

  it('aperçu : rien à poser', () => {
    expect(phraseDuDecompte(decompte({ total_passes: 0, total_laisses: 4 }))).toBe(
      'Rien à poser : les 4 jours choisis restent tels quels.',
    );
  });

  it('enregistré : ce qui a été fait et laissé', () => {
    expect(phraseDuDecompte(decompte({ enregistre: true, total_passes: 12, total_laisses: 1 }))).toBe(
      '12 jours passés en activité partielle, 1 jour laissé tel quel.',
    );
  });
});

describe('lignesDesRaisons et détail', () => {
  const d = decompte({
    total_passes: 1,
    total_laisses: 3,
    laisses_par_raison: { repos: 1, absence: 2 },
    salaries: [],
  });

  it('une ligne par raison, dans l’ordre', () => {
    expect(lignesDesRaisons(d)).toEqual([
      "2 jours : jour d'arrêt, de congé ou d'une autre absence",
      '1 jour : repos, week-end ou jour férié',
    ]);
  });

  it('le détail d’un salarié au forfait', () => {
    expect(
      detailDuSalarie(
        {
          employee_id: 'x',
          nom: 'X',
          forfait_jours: true,
          passes: ['2026-12-04'],
          laisses: [{ date: '2026-12-25', raison: 'repos' }],
          erreurs: [],
        },
        d,
      ),
    ).toBe('1 jour en activité partielle, au forfait jours ; repos, week-end ou jour férié : ven. 25/12/2026');
  });
});
