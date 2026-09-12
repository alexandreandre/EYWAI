import { describe, expect, it } from 'vitest';

import { libelleMontantSaisie } from './seizureFormat';

describe('libelleMontantSaisie', () => {
  it('formate un montant fixe reçu en texte (les décimaux arrivent en chaîne de Supabase)', () => {
    // Gautheron, 12/09 : la page plantait en écran blanc sur "46.49".toFixed.
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
