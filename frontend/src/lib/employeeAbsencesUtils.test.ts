import { describe, expect, it } from 'vitest';
import type { AbsenceBalance } from '@/api/absences';
import {
  formatRhLeaveBalanceDetail,
  getRhLeaveBalanceShortLabel,
  isRhLeaveBalanceVisible,
} from './employeeAbsencesUtils';

describe('employeeAbsencesUtils — soldes RH', () => {
  it('raccourcit les libellés pour la fiche employé', () => {
    expect(getRhLeaveBalanceShortLabel('Congés Payés (période précédente)')).toBe('CP N-1');
    expect(getRhLeaveBalanceShortLabel('Congés Payés')).toBe('CP total');
    expect(getRhLeaveBalanceShortLabel('Type inconnu')).toBe('Type inconnu');
  });

  it('masque le congé sans solde du résumé RH', () => {
    const balance: AbsenceBalance = {
      type: 'Congé sans solde',
      acquired: 0,
      taken: 2,
      remaining: 'N/A',
    };
    expect(isRhLeaveBalanceVisible(balance)).toBe(false);
  });

  it('formate le détail acquis / pris / restant', () => {
    const balance: AbsenceBalance = {
      type: 'Congés Payés',
      acquired: 25,
      taken: 6.5,
      remaining: 18.5,
    };
    expect(formatRhLeaveBalanceDetail(balance)).toBe(
      'Acquis : 25.0 j · Pris : 6.5 j · Restant : 18.5 j',
    );
  });
});
