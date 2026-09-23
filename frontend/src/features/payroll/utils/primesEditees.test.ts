import { describe, expect, it } from 'vitest';
import { ligneDepuisSaisie, primesEditees } from './primesEditees';

const base = { libelle: 'Salaire de base', quantite: 151.67, taux: 14.28, gain: 2165.85 };
const prime = { libelle: 'Prime exceptionnelle', gain: 100, saisie_id: 's-1' };

describe('ligneDepuisSaisie', () => {
  it('porte la saisie à créer et son montant', () => {
    const ligne = ligneDepuisSaisie({
      employee_id: 'emp-1',
      year: 2026,
      month: 8,
      name: 'Prime de fin de chantier',
      amount: 100,
      is_socially_taxed: true,
      is_taxable: true,
    });
    expect(ligne.libelle).toBe('Prime de fin de chantier');
    expect(ligne.gain).toBe(100);
    expect(ligne.nouvelle_saisie).toEqual({
      name: 'Prime de fin de chantier',
      amount: 100,
      is_socially_taxed: true,
      is_taxable: true,
      catalog_prime_id: null,
    });
  });
});

describe('primesEditees', () => {
  it('rien ne change', () => {
    expect(primesEditees({ calcul_du_brut: [base, prime] }, { calcul_du_brut: [base, prime] })).toBe(false);
  });
  it('un montant corrigé', () => {
    expect(
      primesEditees({ calcul_du_brut: [base, prime] }, { calcul_du_brut: [base, { ...prime, gain: 150 }] })
    ).toBe(true);
  });
  it('une prime retirée', () => {
    expect(primesEditees({ calcul_du_brut: [base, prime] }, { calcul_du_brut: [base] })).toBe(true);
  });
  it('une prime ajoutée', () => {
    const nouvelle = { libelle: 'X', gain: 10, nouvelle_saisie: { name: 'X', amount: 10 } };
    expect(primesEditees({ calcul_du_brut: [base] }, { calcul_du_brut: [base, nouvelle] })).toBe(true);
  });
  it('une ligne calculée retouchée n’en est pas une', () => {
    expect(
      primesEditees({ calcul_du_brut: [base] }, { calcul_du_brut: [{ ...base, gain: 2000 }] })
    ).toBe(false);
  });
});
