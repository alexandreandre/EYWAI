import { describe, expect, it } from 'vitest';

import { libelleNiveau, regleAcquittable } from './revueARegarder';

describe('revue à regarder', () => {
  it('nomme les niveaux', () => {
    expect(libelleNiveau('CRITIQUE')).toBe('Critique');
    expect(libelleNiveau('AVERTISSEMENT')).toBe('À relire');
    expect(libelleNiveau('INFO')).toBe('Info');
  });

  it('acquitte les règles du bulletin, pas une alerte du moteur', () => {
    expect(regleAcquittable('B02')).toBe(true);
    expect(regleAcquittable('R03')).toBe(false);
    expect(regleAcquittable('salaire_sous_minimum_conventionnel')).toBe(false);
  });
});
