import { describe, expect, it } from 'vitest';
import { phraseSubrogationDeLaSociete } from './subrogationArret';

describe('phraseSubrogationDeLaSociete', () => {
  it('dit la règle de chaque mode', () => {
    expect(phraseSubrogationDeLaSociete('never')).toContain('pas de subrogation');
    expect(phraseSubrogationDeLaSociete('when_maintien')).toContain('droit au maintien');
    expect(phraseSubrogationDeLaSociete('automatic')).toContain('droit au maintien');
    expect(phraseSubrogationDeLaSociete('at_mp_only')).toContain('accident du travail');
    expect(phraseSubrogationDeLaSociete(undefined)).toBe('Règle de la société');
  });
});
