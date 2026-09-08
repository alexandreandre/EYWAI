import { describe, expect, it } from 'vitest';
import {
  estSurLeMoisCivil,
  formatFr,
  libelleSemaines,
} from './fenetreVariables';
import type { PeriodeVariables } from '@/api/periodeVariables';

const COLORPLAST_JUILLET: PeriodeVariables = {
  debut: '2026-06-22',
  fin: '2026-07-26',
  origine: 'regle',
  semaines: [26, 27, 28, 29, 30],
  mois_civil: ['2026-07-01', '2026-07-31'],
  report_debut: '2026-07-27',
};

const MAJI_JUILLET: PeriodeVariables = {
  debut: '2026-07-01',
  fin: '2026-07-31',
  origine: 'regle',
  semaines: [27, 28, 29, 30, 31],
  mois_civil: ['2026-07-01', '2026-07-31'],
  report_debut: '2026-08-01',
};

describe('formatFr', () => {
  it('rend une date ISO en français', () => {
    expect(formatFr('2026-07-26')).toBe('26/07/2026');
  });
});

describe('libelleSemaines', () => {
  it('donne la première et la dernière', () => {
    expect(libelleSemaines([26, 27, 28, 29, 30])).toBe('semaines 26 à 30');
  });

  it('accorde au singulier sur une seule semaine', () => {
    expect(libelleSemaines([30])).toBe('semaine 30');
  });

  it('rend une chaîne vide sans semaine', () => {
    expect(libelleSemaines([])).toBe('');
  });
});

describe('estSurLeMoisCivil', () => {
  it('est faux quand la fenêtre déborde sur le mois précédent', () => {
    expect(estSurLeMoisCivil(COLORPLAST_JUILLET)).toBe(false);
  });

  it('est vrai pour une société restée au mois civil', () => {
    expect(estSurLeMoisCivil(MAJI_JUILLET)).toBe(true);
  });
});
