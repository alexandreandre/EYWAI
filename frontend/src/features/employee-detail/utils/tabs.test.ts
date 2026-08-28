import { describe, expect, it } from 'vitest';

import {
  TAB_SAISIE,
  TAB_SOLDE_CONGES,
  coercePayrollFocusEmployeeTab,
  normalizeEmployeeDetailTab,
} from './tabs';

describe('coercePayrollFocusEmployeeTab', () => {
  it('conserve les onglets utiles à la paie', () => {
    expect(coercePayrollFocusEmployeeTab('saisie')).toBe('saisie');
    expect(coercePayrollFocusEmployeeTab('calendrier')).toBe('calendrier');
    expect(coercePayrollFocusEmployeeTab(TAB_SOLDE_CONGES)).toBe(TAB_SOLDE_CONGES);
  });

  it('renvoie Primes et autres pour les onglets hors périmètre', () => {
    expect(coercePayrollFocusEmployeeTab('documents')).toBe(TAB_SAISIE);
    expect(coercePayrollFocusEmployeeTab('entretiens')).toBe(TAB_SAISIE);
    expect(coercePayrollFocusEmployeeTab('badgeuse')).toBe(TAB_SAISIE);
    expect(coercePayrollFocusEmployeeTab('suivi_medical')).toBe(TAB_SAISIE);
    expect(
      coercePayrollFocusEmployeeTab(normalizeEmployeeDetailTab('bulletins')),
    ).toBe(TAB_SAISIE);
  });
});
