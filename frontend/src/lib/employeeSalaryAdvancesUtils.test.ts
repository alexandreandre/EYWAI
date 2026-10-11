import { describe, expect, it } from 'vitest';

import type { AdvanceAvailableAmount } from '@/api/saisiesAvances';
import { formatAdvancePlafondSummary } from './employeeSalaryAdvancesUtils';

function disponible(champs: Partial<AdvanceAvailableAmount> = {}): AdvanceAvailableAmount {
  return {
    advance_type: 'avance_salaire',
    daily_salary: 75,
    days_worked: 11,
    outstanding_advances: 0,
    available_amount: 1131.52,
    max_advance_days: 10,
    reference_net_salary: 2263.04,
    reference_payslip_year: 2026,
    reference_payslip_month: 10,
    max_advance_from_net: 1131.52,
    max_advance_net_ratio: 0.5,
    ...champs,
  };
}

/**
 * Avance sur salaire (vidéo G, 11/10/2026) : le bandeau disait « 50 % du net de
 * octobre 2026 ». Devant une voyelle, « de » s'élide.
 */
describe('plafond d’une avance sur salaire', () => {
  it('« d’octobre », « d’août »', () => {
    expect(formatAdvancePlafondSummary(disponible())).toBe("50 % du net d'octobre 2026");
    expect(formatAdvancePlafondSummary(disponible({ reference_payslip_month: 8 }))).toBe(
      "50 % du net d'août 2026",
    );
  });

  it('« de mars »', () => {
    expect(formatAdvancePlafondSummary(disponible({ reference_payslip_month: 3 }))).toBe(
      '50 % du net de mars 2026',
    );
  });
});
