import { describe, expect, it } from 'vitest';

import { moisEnToutesLettres, phraseSaisiePonctuelle } from './libellesSaisie';

describe('phraseSaisiePonctuelle', () => {
  it('nomme le mois du bulletin, pas « le mois en cours »', () => {
    const phrase = phraseSaisiePonctuelle(2026, 8);
    expect(phrase).toContain('août 2026');
    expect(phrase).not.toContain('mois en cours');
  });

  it('sans mois connu, reste vraie', () => {
    expect(phraseSaisiePonctuelle(undefined, undefined)).not.toContain('mois en cours');
  });
});

describe('moisEnToutesLettres', () => {
  it('écrit le mois en français, en minuscules', () => {
    expect(moisEnToutesLettres(2026, 10)).toBe('octobre 2026');
    expect(moisEnToutesLettres(2026, 2)).toBe('février 2026');
  });
});
