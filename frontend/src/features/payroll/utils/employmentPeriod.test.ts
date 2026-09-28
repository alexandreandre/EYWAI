import { describe, expect, it } from 'vitest';
import {
  isEmployeePresentForPayrollMonth,
  payrollEmploymentBlockReason,
  payrollGenerationBlockReason,
} from './employmentPeriod';

describe('employmentPeriod', () => {
  const aurelien = { hire_date: '2026-03-23', contract_end_date: null };

  it.each([1, 2])('bloque le mois %s avant l’embauche', (month) => {
    expect(isEmployeePresentForPayrollMonth(aurelien, 2026, month)).toBe(false);
  });

  it('autorise le mois de l’embauche même si elle intervient en cours de mois', () => {
    expect(isEmployeePresentForPayrollMonth(aurelien, 2026, 3)).toBe(true);
  });

  it('bloque les mois postérieurs à la sortie', () => {
    const employee = { hire_date: '2025-01-01', contract_end_date: '2026-04-10' };
    expect(isEmployeePresentForPayrollMonth(employee, 2026, 5)).toBe(false);
    expect(payrollEmploymentBlockReason(employee, 2026, 5)).toContain('10/04/2026');
  });
});

describe('payrollGenerationBlockReason', () => {
  const nouveau = {
    hire_date: '2026-09-14',
    employment_status: 'en_onboarding',
    missing_payroll_fields: ['Numéro de sécurité sociale', 'Coordonnées bancaires (RIB)'],
  };

  it('une fiche à compléter bloque le bulletin, avec ce qui manque', () => {
    expect(payrollGenerationBlockReason(nouveau, 2026, 9)).toBe(
      'Fiche à compléter : Numéro de sécurité sociale, Coordonnées bancaires (RIB)'
    );
  });

  it("avant l'embauche, c'est la date qui compte", () => {
    expect(payrollGenerationBlockReason(nouveau, 2026, 8)).toContain('14/09/2026');
  });

  it('une fiche complète, ou un départ, ne bloque pas', () => {
    expect(payrollGenerationBlockReason({ ...nouveau, missing_payroll_fields: [] }, 2026, 9)).toBeNull();
    expect(payrollGenerationBlockReason({ ...nouveau, employment_status: 'parti' }, 2026, 9)).toBeNull();
  });
});
