import { describe, expect, it } from 'vitest';
import { deDevant } from './elision';

describe('deDevant', () => {
  it('élide devant une voyelle, accentuée ou en capitale', () => {
    expect(deDevant('Élodie Vasseur')).toBe('d’Élodie Vasseur');
    expect(deDevant('Alice Martin')).toBe('d’Alice Martin');
    expect(deDevant('octobre')).toBe('d’octobre');
    expect(deDevant('août')).toBe('d’août');
  });
  it('élide devant un h muet', () => {
    expect(deDevant('Hélène Roux')).toBe('d’Hélène Roux');
  });
  it('n’élide pas devant une consonne', () => {
    expect(deDevant('Camille Roussel')).toBe('de Camille Roussel');
    expect(deDevant('mars')).toBe('de mars');
  });
  it('ne dit rien d’un nom vide', () => {
    expect(deDevant('')).toBe('');
    expect(deDevant(null)).toBe('');
  });
});
