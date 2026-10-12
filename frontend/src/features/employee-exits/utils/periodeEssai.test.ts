import { describe, expect, it } from 'vitest';
import { AIDE_DELAI_PREVENANCE, OPTIONS_INITIATIVE_ESSAI } from './periodeEssai';
import { preavisASaisir } from './preavis';

// Code du travail L1221-25 et L1221-26 (ouverts le 11/10/2026) : le délai de
// prévenance dépend de qui rompt et du temps de présence ; Martine le calcule.
describe('fin de période d’essai', () => {
  it('demande qui rompt', () => {
    expect(OPTIONS_INITIATIVE_ESSAI).toEqual([
      { value: 'employer', label: "L'employeur" },
      { value: 'employee', label: 'Le salarié' },
    ]);
  });

  it('dit les délais légaux et que Martine verse l’indemnité si l’employeur ne les respecte pas', () => {
    expect(AIDE_DELAI_PREVENANCE).toContain('L1221-25');
    expect(AIDE_DELAI_PREVENANCE).toContain('L1221-26');
    expect(AIDE_DELAI_PREVENANCE).toContain('24 heures');
    expect(AIDE_DELAI_PREVENANCE).toContain('1 mois');
    expect(AIDE_DELAI_PREVENANCE).toContain('indemnité compensatrice');
  });

  it('ne saisit pas de préavis : le délai de prévenance se calcule', () => {
    expect(preavisASaisir('fin_periode_essai')).toBe(false);
  });
});
