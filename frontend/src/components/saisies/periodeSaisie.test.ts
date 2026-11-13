import { describe, expect, it } from 'vitest';
import { erreurPeriodeSaisie, libelleAvecPeriode } from './periodeSaisie';

describe('période imprimée d’une saisie', () => {
  it('porte les dates complètes du maintien, même sur un mois antérieur au versement', () => {
    expect(libelleAvecPeriode('Rappel maintien de salaire', '2026-10-01', '2026-10-05'))
      .toBe('Rappel maintien de salaire du 01/10/2026 au 05/10/2026');
    expect(libelleAvecPeriode('Maintien', '2026-12-30', '2027-01-05'))
      .toBe('Maintien du 30/12/2026 au 05/01/2027');
  });

  it('garde une saisie sans période et sait afficher un seul jour', () => {
    expect(libelleAvecPeriode('Panier', '', '')).toBe('Panier');
    expect(libelleAvecPeriode('Maintien', '2026-10-01', '2026-10-01'))
      .toBe('Maintien du 01/10/2026');
  });

  it.each([
    ['2026-10-01', ''], ['', '2026-10-05'],
    ['2026-10-05', '2026-10-01'], ['2026-02-30', '2026-03-01'],
    ['2026-13-01', '2027-01-01'], ['2026-1-01', '2026-10-05'],
  ])('refuse une période incomplète, impossible ou inversée : %s / %s', (debut, fin) => {
    expect(erreurPeriodeSaisie(debut, fin)).not.toBeNull();
    expect(() => libelleAvecPeriode('Maintien', debut, fin)).toThrow();
  });
});
