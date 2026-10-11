import { describe, expect, it } from 'vitest';
import { INITIATIVE_RETRAITE_PAR_DEFAUT, OPTIONS_INITIATIVE_RETRAITE } from './retraite';

// Code du travail L1237-9 (départ volontaire) et L1237-7 (mise à la retraite),
// ouverts le 11/10/2026 : deux indemnités, deux régimes, deux motifs DSN (039, 038).
describe('retraite : qui prend l’initiative', () => {
  it('propose le départ volontaire et la mise à la retraite par l’employeur', () => {
    expect(OPTIONS_INITIATIVE_RETRAITE).toEqual([
      { value: 'employee', label: 'Le salarié (départ volontaire à la retraite)' },
      { value: 'employer', label: "L'employeur (mise à la retraite)" },
    ]);
  });

  it('par défaut, un départ volontaire', () => {
    expect(INITIATIVE_RETRAITE_PAR_DEFAUT).toBe('employee');
  });
});
