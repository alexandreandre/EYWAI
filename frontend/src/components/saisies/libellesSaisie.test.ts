import { describe, expect, it } from 'vitest';

import {
  LIBELLE_SOUMISE_COTISATIONS,
  LIBELLE_SOUMISE_IMPOT,
  moisEnToutesLettres,
  pastilleSoumise,
  phraseSaisiePonctuelle,
  sousTitreSaisies,
} from './libellesSaisie';

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

describe('vocabulaire commun des saisies', () => {
  it('une seule formulation pour la page, le tableau et la fenêtre', () => {
    expect(LIBELLE_SOUMISE_COTISATIONS).toBe('Soumise à cotisations');
    expect(LIBELLE_SOUMISE_IMPOT).toBe("Soumise à l'impôt");
  });

  it('la pastille du bulletin reprend les mots du tableau', () => {
    expect(pastilleSoumise(true)).toBe('Soumise à cotisations');
    expect(pastilleSoumise(false)).toBe('Non soumise à cotisations');
  });

  it('le sous-titre nomme le mois affiché, jamais « en cours »', () => {
    expect(sousTitreSaisies(2026, 7, false)).toContain('juillet 2026');
    expect(sousTitreSaisies(2026, 7, false)).not.toContain('en cours');
    expect(sousTitreSaisies(2026, 7, true)).toContain('juillet 2026');
    expect(sousTitreSaisies(2026, 7, true)).toContain('ce salarié');
  });
});
