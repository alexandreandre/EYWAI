import { describe, expect, it } from 'vitest';
import { ibanProblem, isValidIban } from './iban';

describe('isValidIban', () => {
  it('accepte des IBAN dont la clé est juste, avec ou sans espaces', () => {
    expect(isValidIban('FR7630001007941234567890185')).toBe(true);
    expect(isValidIban('fr76 3000 1007 9412 3456 7890 185')).toBe(true);
    expect(isValidIban('DE89370400440532013000')).toBe(true);
  });

  it('refuse une clé fausse', () => {
    expect(isValidIban('FR7630001007941234567890186')).toBe(false);
  });

  it('refuse une longueur qui ne correspond pas au pays', () => {
    expect(isValidIban('FR76300010079412')).toBe(false);
    expect(isValidIban('DE8937040044053201300')).toBe(false);
  });
});

describe('ibanProblem', () => {
  it('dit pourquoi, en français', () => {
    expect(ibanProblem('FR7630001007941234567890185')).toBeNull();
    expect(ibanProblem('FR76300010079412')).toContain('27 caractères attendus');
    expect(ibanProblem('FR7630001007941234567890186')).toContain('Clé de contrôle');
  });
});
