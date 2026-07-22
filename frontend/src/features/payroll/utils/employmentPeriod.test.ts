import { describe, expect, it } from 'vitest';
import {
  isEmployeePresentForPayrollMonth,
  payrollEmploymentBlockReason,
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
