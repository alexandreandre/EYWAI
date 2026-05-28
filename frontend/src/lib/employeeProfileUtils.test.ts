import { describe, expect, it } from 'vitest';
import {
  formatProfileAddress,
  formatProfileCurrency,
  formatWeeklyHours,
  maskIban,
} from './employeeProfileUtils';

describe('employeeProfileUtils', () => {
  it('formatProfileAddress joins parts', () => {
    expect(
      formatProfileAddress({ rue: '1 rue Test', code_postal: '75001', ville: 'Paris' })
    ).toBe('1 rue Test, 75001, Paris');
  });

  it('formatProfileAddress returns fallback when empty', () => {
    expect(formatProfileAddress(null)).toBe('Non renseigné');
  });

  it('maskIban shows last four digits', () => {
    expect(maskIban('FR7612345678901234567890123')).toContain('0123');
  });

  it('formatWeeklyHours formats hours', () => {
    expect(formatWeeklyHours(35)).toBe('35 h/semaine');
  });

  it('formatProfileCurrency uses EUR', () => {
    expect(formatProfileCurrency(42.5)).toMatch(/42,50/);
  });
});
