import { describe, expect, it } from 'vitest';

import {
  aideLignesPrevoyance,
  fractionDuTexteTaux,
  texteDuTauxPrevoyance,
} from '@/features/employees/utils/prevoyance';

describe('aide sous la prévoyance ([B4], 12/10/2026)', () => {
  it('un cadre sans ligne : aucune cotisation, il faut saisir les lignes', () => {
    expect(aideLignesPrevoyance(true, 0)).toBe(
      'Saisissez les lignes du contrat de prévoyance : sans ligne, le bulletin d’un cadre ne porte aucune cotisation de prévoyance.',
    );
  });

  it('un non-cadre sans ligne : le barème national', () => {
    expect(aideLignesPrevoyance(false, 0)).toBe('Sans ligne saisie, le barème national s’applique au bulletin.');
  });

  it('avec des lignes, aucune aide', () => {
    expect(aideLignesPrevoyance(true, 2)).toBeNull();
    expect(aideLignesPrevoyance(false, 1)).toBeNull();
  });
});

describe('taux de prévoyance saisis en %, stockés en fraction ([D1], 13/10/2026)', () => {
  it('la fiche stocke une fraction, le champ l’affiche en %', () => {
    expect(texteDuTauxPrevoyance(0.0078)).toBe('0,78');
    expect(texteDuTauxPrevoyance(0.046865)).toBe('4,6865');
    expect(texteDuTauxPrevoyance(0.005601)).toBe('0,5601');
    expect(texteDuTauxPrevoyance(0.08)).toBe('8');
    expect(texteDuTauxPrevoyance(0)).toBe('0');
  });

  it('la saisie en % redevient une fraction, virgule ou point', () => {
    expect(fractionDuTexteTaux('0,78')).toBe(0.0078);
    expect(fractionDuTexteTaux('1.5')).toBe(0.015);
    expect(fractionDuTexteTaux(' 8 ')).toBe(0.08);
    expect(fractionDuTexteTaux('')).toBe(0);
  });

  it('une saisie qui n’est pas un nombre ne devient pas un taux', () => {
    expect(fractionDuTexteTaux('abc')).toBeNull();
    expect(fractionDuTexteTaux('0,7,8')).toBeNull();
  });

  it.each([0.046865, 0.005601, 0.0078])(
    'retaper le taux affiché rend exactement la valeur stockée (%s)',
    (stocke) => {
      expect(fractionDuTexteTaux(texteDuTauxPrevoyance(stocke))).toBe(stocke);
    },
  );
});
