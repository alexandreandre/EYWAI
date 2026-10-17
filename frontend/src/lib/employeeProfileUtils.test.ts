import { describe, expect, it } from 'vitest';
import {
  formatProfileAddress,
  formatProfileCurrency,
  formatPartSalariale,
  formatWeeklyHours,
  getDisplayEmployeeEmail,
  getDisplayEmployeeUsername,
  isDsnImportPlaceholderEmail,
  maskIban,
} from './employeeProfileUtils';

describe('part salariale affichée dans l’espace salarié', () => {
  it('la prévoyance est un taux stocké en fraction : 0,0078 se lit « 0,78 % », jamais « 0,01 € »', () => {
    expect(formatPartSalariale({ salarial: 0.0078 }, 'prevoyance')).toBe('0,78 %');
    expect(formatPartSalariale({ salarial: 0.046865 }, 'prevoyance')).toBe('4,6865 %');
  });

  it('la mutuelle reste un montant en euros', () => {
    expect(formatPartSalariale({ montant_salarial: 17.62 }, 'mutuelle')).toBe(formatProfileCurrency(17.62));
  });

  it('sans valeur, rien ne s’affiche', () => {
    expect(formatPartSalariale({}, 'prevoyance')).toBeNull();
    expect(formatPartSalariale({}, 'mutuelle')).toBeNull();
  });
});

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
    expect(isDsnImportPlaceholderEmail('gestionnaire.paie@eywai.access.local')).toBe(true);
    expect(isDsnImportPlaceholderEmail('admin.societe@users.eywai')).toBe(true);
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
