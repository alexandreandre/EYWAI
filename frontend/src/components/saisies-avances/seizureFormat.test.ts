import { describe, expect, it } from 'vitest';

import { libelleMontantSaisie, libellePersonnesACharge, personnesACharge } from './seizureFormat';

describe('libelleMontantSaisie', () => {
  it('formate un montant fixe reçu en texte (les décimaux arrivent en chaîne de Supabase)', () => {
    // Morande, 12/09 : la page plantait en écran blanc sur "46.49".toFixed.
    expect(
      libelleMontantSaisie({ calculation_mode: 'fixe', amount: '46.49' as unknown as number })
    ).toBe('46.49€');
  });

  it('formate un montant fixe numérique', () => {
    expect(libelleMontantSaisie({ calculation_mode: 'fixe', amount: 120 })).toBe('120.00€');
  });

  it('affiche le pourcentage', () => {
    expect(libelleMontantSaisie({ calculation_mode: 'pourcentage', percentage: 10 })).toBe('10%');
  });

  it('retombe sur le barème légal', () => {
    expect(libelleMontantSaisie({ calculation_mode: 'barème_legal' })).toBe('Barème légal');
    expect(libelleMontantSaisie({ calculation_mode: 'fixe', amount: undefined })).toBe(
      'Barème légal'
    );
  });
});

describe('personnesACharge', () => {
  // Le barème légal relève chaque seuil par personne à charge (R3252-3) : un
  // nombre entier, jamais négatif ; un champ vide vaut aucune.
  it('lit un entier positif', () => {
    expect(personnesACharge('2')).toBe(2);
  });

  it('vide, négatif ou illisible : aucune', () => {
    expect(personnesACharge('')).toBe(0);
    expect(personnesACharge('-1')).toBe(0);
    expect(personnesACharge('abc')).toBe(0);
  });

  it('arrondit à l’entier inférieur', () => {
    expect(personnesACharge('1.7')).toBe(1);
  });
});

describe('libellePersonnesACharge', () => {
  it('dit le nombre en clair', () => {
    expect(libellePersonnesACharge(0)).toBe('Aucune');
    expect(libellePersonnesACharge(undefined)).toBe('Aucune');
    expect(libellePersonnesACharge(1)).toBe('1 personne');
    expect(libellePersonnesACharge(3)).toBe('3 personnes');
  });
});
