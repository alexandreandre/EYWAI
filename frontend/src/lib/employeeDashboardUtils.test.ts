import { describe, expect, it } from 'vitest';
import type { AbsenceRequest } from '@/api/absences';
import {
  buildAbsenceCalendarModifiers,
  formatCurrency,
  formatCumulsMonthLabel,
  getNextValidatedAbsenceDate,
  parseAbsenceDayLocal,
  pickDisplayPayslip,
  type PayslipInfo,
} from './employeeDashboardUtils';

const payslip = (month: number, year: number, id = 'p1'): PayslipInfo => ({
  id,
  month,
  year,
  name: `Bulletin ${month}/${year}`,
  url: '/x',
  net_a_payer: 2500,
});

describe('employeeDashboardUtils', () => {
  it('pickDisplayPayslip prefers M-1 when present', () => {
    const today = new Date();
    const prevMonth = today.getMonth() === 0 ? 12 : today.getMonth();
    const prevYear =
      today.getMonth() === 0 ? today.getFullYear() - 1 : today.getFullYear();
    const payslips = [
      payslip(prevMonth, prevYear, 'm1'),
      payslip(1, today.getFullYear(), 'old'),
    ];
    const result = pickDisplayPayslip(payslips);
    expect(result?.label).toBe('m1');
    expect(result?.payslip.id).toBe('m1');
  });

  it('pickDisplayPayslip falls back to latest when no M-1', () => {
    const payslips = [payslip(1, 2020, 'a'), payslip(6, 2024, 'b')];
    const result = pickDisplayPayslip(payslips);
    expect(result?.label).toBe('latest');
    expect(result?.payslip.id).toBe('b');
  });

  it('pickDisplayPayslip returns null for empty list', () => {
    expect(pickDisplayPayslip([])).toBeNull();
  });

  it('formatCurrency returns N/A for null', () => {
    expect(formatCurrency(null)).toBe('N/A');
    expect(formatCurrency(undefined)).toBe('N/A');
  });

  it('formatCurrency formats EUR in fr-FR', () => {
    const s = formatCurrency(1234.5);
    expect(s).toMatch(/1[\s\u202f]?234,50/);
    expect(s).toMatch(/€/);
  });

  it('formatCumulsMonthLabel rejects invalid months', () => {
    expect(formatCumulsMonthLabel(0)).toBeNull();
    expect(formatCumulsMonthLabel(13)).toBeNull();
    expect(formatCumulsMonthLabel(6)).toMatch(/juin/i);
  });

  it('parseAbsenceDayLocal parses YYYY-MM-DD at local midnight', () => {
    const d = parseAbsenceDayLocal('2099-06-15');
    expect(d.getFullYear()).toBe(2099);
    expect(d.getMonth()).toBe(5);
    expect(d.getDate()).toBe(15);
  });

  it('getNextValidatedAbsenceDate ignores past and non-validated', () => {
    const history: AbsenceRequest[] = [
      {
        id: '1',
        created_at: '',
        employee_id: 'e',
        type: 'conge_paye',
        selected_days: ['2099-12-31', '2099-06-15'],
        comment: null,
        status: 'validated',
        manager_id: null,
        attachment_url: null,
        filename: null,
      },
      {
        id: '2',
        created_at: '',
        employee_id: 'e',
        type: 'rtt',
        selected_days: ['2000-01-01'],
        comment: null,
        status: 'pending',
        manager_id: null,
        attachment_url: null,
        filename: null,
      },
    ];
    const next = getNextValidatedAbsenceDate(history);
    expect(next?.getTime()).toBe(parseAbsenceDayLocal('2099-06-15').getTime());
  });

  it('buildAbsenceCalendarModifiers uses weekends when no API days', () => {
    const month = new Date(2026, 4, 1);
    const today = new Date(2026, 4, 15);
    const mods = buildAbsenceCalendarModifiers([], month, today, null);
    expect(mods.weekend?.length).toBeGreaterThan(0);
    expect(mods.aujourdhui).toHaveLength(1);
  });
});
