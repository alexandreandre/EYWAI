import { describe, expect, it } from 'vitest';

import {
  LIBELLE_SOUMISE_COTISATIONS,
  LIBELLE_SOUMISE_IMPOT,
  messageBulletinsARecalculer,
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

describe('messageBulletinsARecalculer', () => {
  const nom = (id: string) => ({ a: 'Camille Test', b: 'Dominique Essai', c: 'Claude Exemple', d: 'Alix Modèle' })[id] ?? 'Inconnu';
  const cible = (employee_id: string, month = 10) => ({ employee_id, year: 2026, month });

  it('un seul bulletin : le nom du salarié et le mois', () => {
    expect(messageBulletinsARecalculer([cible('a')], nom)).toBe(
      "Le bulletin d'octobre 2026 de Camille Test est à recalculer.",
    );
  });

  it("élision devant une voyelle, pas devant une consonne", () => {
    expect(messageBulletinsARecalculer([cible('a', 8)], nom)).toContain("d'août 2026");
    expect(messageBulletinsARecalculer([cible('a', 9)], nom)).toContain('de septembre 2026');
  });

  it('plusieurs bulletins : accordé au pluriel, noms écrits', () => {
    expect(messageBulletinsARecalculer([cible('a'), cible('b')], nom)).toBe(
      "Les bulletins d'octobre 2026 de Camille Test et Dominique Essai sont à recalculer.",
    );
  });

  it('beaucoup de bulletins : le nombre, sans liste interminable', () => {
    const texte = messageBulletinsARecalculer([cible('a'), cible('b'), cible('c'), cible('d')], nom);
    expect(texte).toBe("4 bulletins d'octobre 2026 sont à recalculer.");
  });

  it('aucun bulletin : rien à dire', () => {
    expect(messageBulletinsARecalculer([], nom)).toBeNull();
  });

  it('recherche impossible : le dit au lieu de se taire', () => {
    expect(messageBulletinsARecalculer(null, nom)).toContain('à recalculer');
  });
});

describe('messageBulletinsARecalculer : élision devant le nom', () => {
  const nom = (id: string) => ({ a: 'Élodie Test', b: 'Camille Test', c: 'Hélène Essai' })[id] ?? 'Inconnu';
  const cible = (employee_id: string) => ({ employee_id, year: 2026, month: 10 });

  it("« d'Élodie Test » et non « de Élodie Test »", () => {
    expect(messageBulletinsARecalculer([cible('a')], nom)).toBe(
      "Le bulletin d'octobre 2026 d'Élodie Test est à recalculer.",
    );
  });
  it('dans la liste, seul le premier nom suit « de »', () => {
    expect(messageBulletinsARecalculer([cible('a'), cible('b')], nom)).toBe(
      "Les bulletins d'octobre 2026 d'Élodie Test et Camille Test sont à recalculer.",
    );
  });
});
