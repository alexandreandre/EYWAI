import { describe, expect, it } from 'vitest';
import { modifierLeJour } from './modificationDuJour';

describe('modifierLeJour', () => {
  const fixe = { jour: 1, heures: 6.75, type: 'travail', heures_fixees_par_fichier: true };

  it('une heure, un type ou une nature changés à la main : plus « retenues du fichier »', () => {
    expect(modifierLeJour(fixe, { heures: 7 }).heures_fixees_par_fichier).toBe(false);
    expect(modifierLeJour(fixe, { type: 'conge' }).heures_fixees_par_fichier).toBe(false);
    expect(modifierLeJour(fixe, { nature: 'prevu' }).heures_fixees_par_fichier).toBe(false);
  });

  it('la même valeur retapée ne compte pas comme une modification', () => {
    expect(modifierLeJour(fixe, { heures: 6.75 }).heures_fixees_par_fichier).toBe(true);
  });
});
