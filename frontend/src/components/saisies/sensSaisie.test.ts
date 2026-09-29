import { describe, expect, it } from 'vitest';

import { champsDeLaSaisie } from './sensSaisie';

const cases = { is_socially_taxed: true, is_taxable: true };

describe('champsDeLaSaisie', () => {
  it('une prime garde son montant et ses cases', () => {
    expect(champsDeLaSaisie('prime', 150, cases)).toEqual({ amount: 150, sur_le_net: false, ...cases });
  });

  it('une retenue sur le net part en négatif, hors cotisations et impôt', () => {
    expect(champsDeLaSaisie('retenue_net', 419.75, cases)).toEqual({
      amount: -419.75,
      sur_le_net: true,
      is_socially_taxed: false,
      is_taxable: false,
    });
  });

  it('une retenue tapée en négatif ne devient pas un versement', () => {
    expect(champsDeLaSaisie('retenue_net', -419.75, cases).amount).toBe(-419.75);
  });

  it('un versement sur le net reste positif', () => {
    expect(champsDeLaSaisie('versement_net', 300, cases)).toMatchObject({ amount: 300, sur_le_net: true });
  });
});
