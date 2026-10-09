import { describe, expect, it } from 'vitest';
import { formatValeur } from './PayslipComparisonTab';

// Constat du 09/10/2026 : les heures de la comparaison N-1 s'affichaient en euros.
describe('formatValeur', () => {
  it('affiche des heures en heures', () => {
    expect(formatValeur(151.67, 'h')).toBe('151,67 h');
  });
  it('affiche un nombre sans unité', () => {
    expect(formatValeur(3, 'nombre')).toBe('3');
  });
  it('affiche un montant en euros, y compris sans unité donnée', () => {
    expect(formatValeur(2450, 'eur').replace(/\s/g, ' ')).toBe('2 450,00 €');
    expect(formatValeur(2450, undefined).replace(/\s/g, ' ')).toBe('2 450,00 €');
  });
  it('affiche un tiret sans valeur', () => {
    expect(formatValeur(null, 'h')).toBe('—');
  });
});
