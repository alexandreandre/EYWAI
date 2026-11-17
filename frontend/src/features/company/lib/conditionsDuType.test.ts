import { describe, expect, it } from 'vitest';

import { conditionsDuType, panierEnMontantFixe } from './conditionsDuType';

describe('conditionsDuType (Lyon, 17/11)', () => {
  it('un montant fixe perd les conditions d’astreinte et garde les salariés', () => {
    expect(
      conditionsDuType('fixed_monthly', { employee_ids: ['e1'], requires_astreinte: true, rate_mode: 'x' }),
    ).toEqual({ employee_ids: ['e1'] });
  });
  it('une règle garde ses propres conditions', () => {
    expect(conditionsDuType('per_worked_day', { min_heures: 6, shift_type_codes: ['N'] })).toEqual({ min_heures: 6 });
  });
});

describe('panierEnMontantFixe', () => {
  it('repère un panier en montant fixe mensuel', () => {
    expect(panierEnMontantFixe('Panier Chauffeur', 'fixed_monthly')).toBe(true);
    expect(panierEnMontantFixe('Panier Chauffeur', 'per_worked_day')).toBe(false);
    expect(panierEnMontantFixe('Prime poste difficile', 'fixed_monthly')).toBe(false);
  });
});
