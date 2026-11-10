import { describe, expect, it } from 'vitest';

import { lireNombre } from './nombreSaisi';

describe('lireNombre', () => {
  it('accepte le point et la virgule', () => {
    expect(lireNombre('12,5')).toBe(12.5);
    expect(lireNombre('12.5')).toBe(12.5);
    expect(lireNombre('-3,25')).toBe(-3.25);
    expect(lireNombre('0,5')).toBe(0.5);
    expect(lireNombre(',5')).toBe(0.5);
    expect(lireNombre('3,')).toBe(3);
  });

  it('ignore les espaces, l’euro et les séparateurs de milliers', () => {
    expect(lireNombre('1 234,56')).toBe(1234.56);
    expect(lireNombre('1 234,56 €')).toBe(1234.56);
    expect(lireNombre('1.234,56')).toBe(1234.56);
    expect(lireNombre('1,234.56')).toBe(1234.56);
  });

  it('rend null sur un texte illisible, jamais zéro', () => {
    expect(lireNombre('')).toBeNull();
    expect(lireNombre('-')).toBeNull();
    expect(lireNombre('abc')).toBeNull();
    expect(lireNombre('1,2,3')).toBeNull();
    expect(lireNombre(null)).toBeNull();
    expect(lireNombre(7)).toBe(7);
  });
});
