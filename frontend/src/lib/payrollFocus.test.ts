import { describe, expect, it } from 'vitest';

import {
  PAYROLL_FOCUS_NAV_URLS,
  isPayrollFocusActive,
  isPayrollFocusAllowed,
} from './payrollFocus';

describe('PAYROLL_FOCUS_NAV_URLS', () => {
  it('contient exactement 19 entrées, sans doublon', () => {
    expect(PAYROLL_FOCUS_NAV_URLS).toHaveLength(19);
    expect(new Set(PAYROLL_FOCUS_NAV_URLS).size).toBe(19);
  });
});

describe('isPayrollFocusAllowed', () => {
  it('autorise chaque entrée de menu du périmètre', () => {
    for (const url of PAYROLL_FOCUS_NAV_URLS) {
      expect(isPayrollFocusAllowed(url)).toBe(true);
    }
  });

  it('autorise les sous-routes ouvertes depuis ces écrans', () => {
    expect(isPayrollFocusAllowed('/employees/abc-123')).toBe(true);
    expect(isPayrollFocusAllowed('/payroll/abc-123')).toBe(true);
    expect(isPayrollFocusAllowed('/payslips/abc-123/edit')).toBe(true);
  });

  it('refuse les écrans hors périmètre', () => {
    for (const url of [
      '/cse',
      '/formation',
      '/recruitment',
      '/onboarding',
      '/employee-exits',
      '/trial-periods',
      '/teams',
      '/documents',
      '/residence-permits',
      '/medical-follow-up',
      '/annual-reviews',
      '/analytics',
      '/analytics-paie',
      '/analytics-gestion',
      '/users',
      '/company',
      '/planning',
      '/badgeuse-rh',
      '/augmentations-et-promotions',
    ]) {
      expect(isPayrollFocusAllowed(url)).toBe(false);
    }
  });

  it('ignore la query string et le fragment', () => {
    expect(isPayrollFocusAllowed('/employees?alert=deadlines')).toBe(true);
    expect(isPayrollFocusAllowed('/annual-reviews?focus=upcoming')).toBe(false);
    expect(isPayrollFocusAllowed('/formation#entretiens')).toBe(false);
  });

  it('tolère la barre oblique finale', () => {
    expect(isPayrollFocusAllowed('/exports/')).toBe(true);
    expect(isPayrollFocusAllowed('/cse/')).toBe(false);
  });

  it('ne confond pas deux chemins de même préfixe textuel', () => {
    expect(isPayrollFocusAllowed('/employee-loans')).toBe(true);
    expect(isPayrollFocusAllowed('/employee-exits')).toBe(false);
  });
});

describe('isPayrollFocusActive', () => {
  it('est actif pour un compte client', () => {
    expect(isPayrollFocusActive({ role: 'rh', email: 'gaelle.bouali@maji-invest.fr' })).toBe(true);
    expect(isPayrollFocusActive({ role: 'admin', email: 'vanessa.amate@maji-invest.fr' })).toBe(true);
  });

  it('est inactif pour un administrateur plateforme', () => {
    expect(isPayrollFocusActive({ role: 'rh', is_platform_admin: true })).toBe(false);
    expect(isPayrollFocusActive({ role: 'rh', is_super_admin: true })).toBe(false);
  });

  it('est inactif pour un e-mail de la liste de contournement, quelle que soit la casse', () => {
    expect(isPayrollFocusActive({ role: 'rh', email: 'alexandreandre2004@gmail.com' })).toBe(false);
    expect(isPayrollFocusActive({ role: 'rh', email: 'Alexandreandre2004@GMAIL.com ' })).toBe(false);
  });

  it('est inactif sans utilisateur', () => {
    expect(isPayrollFocusActive(null)).toBe(false);
    expect(isPayrollFocusActive(undefined)).toBe(false);
  });
});
