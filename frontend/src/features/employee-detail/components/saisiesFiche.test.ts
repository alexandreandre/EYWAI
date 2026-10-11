import { describe, expect, it } from 'vitest';

import { presentationSaisieFiche } from './saisiesFiche';

/**
 * Onglet « Primes et autres » de la fiche (inventaire G, [G2]) : une retenue sur
 * le net (acompte, report d'un net négatif) s'affichait « -100.00 € » avec
 * « Non / Non », sans dire « Retenue sur le net » ; les heures sup déclarées
 * depuis un bulletin s'y lisaient « 0.00 € ». La fiche dit ce que dit la page
 * des primes, montants à la française.
 */
describe('une saisie du mois sur la fiche', () => {
  it('une retenue sur le net le dit, comme sur la page des primes', () => {
    expect(
      presentationSaisieFiche({
        name: 'Acompte versé le 5 octobre',
        amount: -100,
        is_socially_taxed: false,
        is_taxable: false,
        sur_le_net: true,
      }),
    ).toEqual({
      libelle: 'Acompte versé le 5 octobre',
      montant: '−100,00 €',
      pastille: 'Retenue sur le net',
      cotisations: 'Sur le net',
      impot: 'Non',
    });
  });

  it('un report de net négatif saisi avant la case est aussi une retenue', () => {
    const vue = presentationSaisieFiche({
      name: 'Report NAP négatif 10/2026',
      amount: -801.25,
      is_socially_taxed: false,
      is_taxable: false,
    });
    expect(vue.montant).toBe('−801,25 €');
    expect(vue.pastille).toBe('Retenue sur le net');
  });

  it('un versement sur le net le dit aussi', () => {
    const vue = presentationSaisieFiche({
      name: 'Avance',
      amount: 300,
      is_socially_taxed: false,
      is_taxable: false,
      sur_le_net: true,
    });
    expect(vue.pastille).toBe('Versement sur le net');
    expect(vue.cotisations).toBe('Sur le net');
  });

  it('une prime : montant à la française, Oui / Non', () => {
    expect(
      presentationSaisieFiche({
        name: 'Prime exceptionnelle',
        amount: 1150,
        is_socially_taxed: true,
        is_taxable: true,
      }),
    ).toEqual({
      libelle: 'Prime exceptionnelle',
      montant: '1 150,00 €',
      pastille: null,
      cotisations: 'Oui',
      impot: 'Oui',
    });
  });

  it('les heures sup déclarées au bulletin se disent en heures', () => {
    expect(
      presentationSaisieFiche({
        name: 'Heures supplémentaires (corrigées au bulletin)',
        amount: 0,
        payroll_quantity: 4,
        is_socially_taxed: true,
        is_taxable: true,
      }),
    ).toEqual({
      libelle: 'Heures sup. corrigées au bulletin : 4 h à 25 %',
      montant: '4 h',
      pastille: null,
      cotisations: '—',
      impot: '—',
    });
  });
});
