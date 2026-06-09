import { describe, expect, it } from 'vitest';
import { isEmployeeOnlyPath, resolvePostLoginPath } from '@/lib/routeAccess';

describe('routeAccess', () => {
  it('identifie les chemins réservés à l’espace collaborateur', () => {
    expect(isEmployeeOnlyPath('/calendar')).toBe(true);
    expect(isEmployeeOnlyPath('/absences')).toBe(true);
    expect(isEmployeeOnlyPath('/employee/documents')).toBe(true);
    expect(isEmployeeOnlyPath('/payslips')).toBe(true);
    expect(isEmployeeOnlyPath('/employees')).toBe(false);
    expect(isEmployeeOnlyPath('/expenses')).toBe(false);
  });

  it('autorise l’édition RH des bulletins hors espace collaborateur', () => {
    expect(isEmployeeOnlyPath('/payslips/abc-123/edit')).toBe(false);
    expect(
      resolvePostLoginPath('/payslips/abc-123/edit', { role: 'rh' }),
    ).toBe('/payslips/abc-123/edit');
  });

  it('renvoie vers l’accueil RH si la route cible est espace employé', () => {
    expect(
      resolvePostLoginPath('/calendar', { role: 'rh' }),
    ).toBe('/');
    expect(
      resolvePostLoginPath('/calendar', { role: 'admin' }),
    ).toBe('/');
  });

  it('conserve la route cible pour un collaborateur', () => {
    expect(
      resolvePostLoginPath('/calendar', { role: 'collaborateur' }),
    ).toBe('/calendar');
  });

  it('conserve les routes RH partagées après connexion RH', () => {
    expect(
      resolvePostLoginPath('/expenses', { role: 'rh' }),
    ).toBe('/expenses');
  });
});
