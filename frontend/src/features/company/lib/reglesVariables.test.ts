import { describe, expect, it } from 'vitest';

import {
  AIDE_INDEMNITE_TRAJET,
  LIBELLE_INDEMNITE_TRAJET,
  REGLES_SANS_MONTANT,
  RULE_TYPE_LABELS,
} from '@/features/company/lib/reglesVariables';

describe('indemnité de trajet domicile-travail ([B6], 12/10/2026)', () => {
  // Le moteur ne paie l’indemnité de la fiche que par une règle
  // `transport_domicile_travail` des Variables de paie ; la liste de l’écran
  // ne proposait pas ce type : impossible de la créer.
  it('le type de règle se choisit à l’écran', () => {
    expect(RULE_TYPE_LABELS.transport_domicile_travail).toBe('Indemnité de trajet domicile-travail');
  });

  it('son montant vient de chaque fiche, pas de la règle', () => {
    expect(REGLES_SANS_MONTANT.has('transport_domicile_travail')).toBe(true);
  });

  it('un seul texte pour la création et la fiche, qui dit qu’il faut la règle', () => {
    expect(LIBELLE_INDEMNITE_TRAJET).toBe('Indemnité de trajet domicile-travail (€ net/mois)');
    expect(AIDE_INDEMNITE_TRAJET).toContain('Variables de paie');
    expect(AIDE_INDEMNITE_TRAJET).toContain('Saisies > Primes');
    expect(AIDE_INDEMNITE_TRAJET).not.toContain('versé en net chaque mois');
  });
});
