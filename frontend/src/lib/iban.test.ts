import { describe, expect, it } from 'vitest';
import { avertissementIban, ibanBienForme, ibanProblem, isValidIban } from './iban';

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

describe('un IBAN faux mais bien formé avertit sans bloquer', () => {
  it('bien formé : pays, clé, 15 à 34 caractères, sans regarder la clé ni la longueur du pays', () => {
    expect(ibanBienForme('FR7630001007941234567890186')).toBe(true);
    expect(ibanBienForme('FR76300010079412')).toBe(true);
    expect(ibanBienForme('FR76 1234')).toBe(false);
    expect(ibanBienForme('')).toBe(false);
  });

  it('l’avertissement dit le problème et ce qu’il bloque', () => {
    expect(avertissementIban('FR7630001007941234567890186')).toBe(
      "Clé de contrôle de l'IBAN incorrecte : vérifiez la saisie. La fiche s'enregistre, " +
        'mais le virement des salaires restera bloqué tant que cet IBAN n’est pas corrigé.'
    );
  });

  it('rien à dire pour un salarié payé sans virement', () => {
    expect(avertissementIban('FR7630001007941234567890186', 'cheque')).toBeNull();
    expect(avertissementIban('FR7630001007941234567890186', 'virement')).not.toBeNull();
  });

  it('rien à dire pour un IBAN juste, vide ou mal formé (ce dernier est refusé)', () => {
    expect(avertissementIban('FR7630001007941234567890185')).toBeNull();
    expect(avertissementIban('')).toBeNull();
    expect(avertissementIban('FR76 1234')).toBeNull();
  });
});
