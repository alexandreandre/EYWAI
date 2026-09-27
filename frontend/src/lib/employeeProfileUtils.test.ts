import { describe, expect, it } from 'vitest';
import {
  formatProfileAddress,
  formatProfileCurrency,
  formatWeeklyHours,
  getDisplayEmployeeEmail,
  getDisplayEmployeeUsername,
  isDsnImportPlaceholderEmail,
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

  it('isDsnImportPlaceholderEmail detects import suffix', () => {
    expect(
      isDsnImportPlaceholderEmail('import.samir.cavanot.353238@498610351.dsn-import.local'),
    ).toBe(true);
    expect(isDsnImportPlaceholderEmail('prenom@cartol.fr')).toBe(false);
  });

  it('isDsnImportPlaceholderEmail detects every fabricated domain', () => {
    expect(isDsnImportPlaceholderEmail('import.abc123@dsn-import.eywai.fr')).toBe(true);
    expect(isDsnImportPlaceholderEmail('gaelle.cavotin@eywai.access.local')).toBe(true);
    expect(isDsnImportPlaceholderEmail('vanessa.barague@users.eywai')).toBe(true);
    expect(isDsnImportPlaceholderEmail('dupontvanessa@yahoo.fr')).toBe(false);
    expect(isDsnImportPlaceholderEmail('')).toBe(false);
    expect(isDsnImportPlaceholderEmail(null)).toBe(false);
  });

  it('getDisplayEmployeeEmail hides placeholder', () => {
    expect(getDisplayEmployeeEmail('import.x@498610351.dsn-import.local')).toBeNull();
    expect(getDisplayEmployeeEmail('prenom@cartol.fr')).toBe('prenom@cartol.fr');
  });

  it('getDisplayEmployeeUsername hides login before activation', () => {
    expect(
      getDisplayEmployeeUsername(
        'import.samir.cavanot.353238@498610351.dsn-import.local',
        'import.samir.cavanot.353238',
      ),
    ).toBeNull();
    expect(getDisplayEmployeeUsername('prenom@cartol.fr', 'samir.cavanot')).toBe('samir.cavanot');
  });
});
