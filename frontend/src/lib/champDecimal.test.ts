import { describe, expect, it } from 'vitest';
import { ecrireDecimal, lireDecimal } from './champDecimal';

describe('lireDecimal', () => {
  it('lit la virgule comme le point', () => {
    expect(lireDecimal('7,60')).toBe(7.6);
    expect(lireDecimal('7.60')).toBe(7.6);
    expect(lireDecimal(' 7,5 € ')).toBe(7.5);
  });
  it('garde la frappe en cours lisible (« 7, » vaut 7)', () => {
    expect(lireDecimal('7,')).toBe(7);
    expect(lireDecimal(',5')).toBe(0.5);
  });
  it('vide → null, texte → NaN', () => {
    expect(lireDecimal('')).toBeNull();
    expect(lireDecimal('  ')).toBeNull();
    expect(lireDecimal('abc')).toBeNaN();
    expect(lireDecimal('7,6,1')).toBeNaN();
    expect(lireDecimal(',')).toBeNaN();
  });
});

describe('ecrireDecimal', () => {
  it('affiche à la française', () => {
    expect(ecrireDecimal(7.6)).toBe('7,6');
    expect(ecrireDecimal(10)).toBe('10');
    expect(ecrireDecimal(null)).toBe('');
    expect(ecrireDecimal(undefined)).toBe('');
  });
});

describe('lireDecimal, espaces insécables', () => {
  it('ignore les espaces des montants copiés (1 234,50)', () => {
    expect(lireDecimal('1 234,50')).toBe(1234.5);
    expect(lireDecimal('1 234,50')).toBe(1234.5);
  });
});
