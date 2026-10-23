import { describe, expect, it } from 'vitest';

import {
  PHRASE_RESTAURATION,
  VERSIONS_CONSERVEES,
  intituleDeVersion,
  libelleBoutonRestaurer,
  phraseConservation,
  remplaceePar,
  textesConfirmationRestauration,
} from './historiqueVersions';

describe('phraseConservation', () => {
  it('dit le plafond de versions conservées', () => {
    expect(VERSIONS_CONSERVEES).toBe(10);
    expect(phraseConservation([3, 4])).toContain('10 dernières versions');
  });

  it("à la dixième, prévient que la plus ancienne partira à la prochaine", () => {
    const versions = [12, 13, 14, 15, 16, 17, 18, 19, 20, 21];
    const phrase = phraseConservation(versions);
    expect(phrase).toContain('version 12');
    expect(phrase).toContain('prochaine');
    expect(phrase).toContain('PDF');
  });

  it("avant la dixième, ne fait pas peur", () => {
    expect(phraseConservation([1, 2, 3])).not.toContain('prochaine');
  });
});

describe('textesConfirmationRestauration', () => {
  const t = textesConfirmationRestauration(4, {
    reviennent: ['Prime « Prime de jeu » : 300,00 €', 'Correction de la ligne « Salaire de base » : Avenant'],
    remplacees: [],
    retirees: ['Correction de la ligne « Mutuelle » : Tarif erroné', 'Correction de la ligne « Impôt » : Taux personnalisé'],
  });

  it('dit ce qui revient, corrections de ligne comprises', () => {
    expect(t.titre).toBe('Restaurer la version 4 ?');
    const reviennent = t.sections.find((s) => s.titre === 'Reviennent');
    expect(reviennent?.lignes).toContain('Correction de la ligne « Salaire de base » : Avenant');
  });

  it('dit, avant de confirmer, les corrections du moment qui seront retirées', () => {
    const retirees = t.sections.find((s) => s.titre === 'Seront retirées');
    expect(retirees?.lignes).toEqual([
      'Correction de la ligne « Mutuelle » : Tarif erroné',
      'Correction de la ligne « Impôt » : Taux personnalisé',
    ]);
    expect(t.sections.map((s) => s.titre)).not.toContain('Seront remplacées');
  });

  it('dit celles qui seront remplacées', () => {
    const r = textesConfirmationRestauration(2, {
      reviennent: [],
      remplacees: ['Correction de la ligne « Salaire de base » : Taux du jour (remplacée par celle de la version : Avenant)'],
      retirees: [],
    });
    expect(r.sections.map((s) => s.titre)).toEqual(['Seront remplacées']);
  });

  it('ce qui ne revient pas, et le recalcul', () => {
    expect(t.fin).toContain('recalculé');
    expect(t.fin).toContain('planning');
    expect(t.fin).toContain('historique');
    expect(t.fin).not.toContain('cotisations sont ceux du moment');
  });

  it('une version identique : rien ne change, et il le dit', () => {
    const r = textesConfirmationRestauration(3, { reviennent: [], remplacees: [], retirees: [] });
    expect(r.sections).toEqual([]);
    expect(r.rien).toMatch(/rien ne change/i);
  });

  it('sans aperçu lu, le dit au lieu de taire les corrections', () => {
    const r = textesConfirmationRestauration(3, null);
    expect(r.sections).toEqual([]);
    expect(r.rien).toContain('pas pu être lu');
    expect(r.rien).toContain('corrections de ligne');
    expect(r.rien).toContain('régularisations');
  });

  it('le bouton confirme l’action, pas « OK »', () => {
    expect(t.confirmer).toBe('Restaurer ces heures sup, primes et corrections');
  });
});

describe('libelleBoutonRestaurer', () => {
  it('ne promet pas toute la version, et nomme les corrections', () => {
    expect(libelleBoutonRestaurer).toBe('Restaurer heures sup, primes et corrections');
  });
});

describe('intitulé d’une version : ce qu’elle contient, pas le changement qui l’a remplacée', () => {
  it('dit ce qui revient si on la restaure', () => {
    const entree = {
      changes_summary: '1 prime retirée',
      contenu: ['Heures sup 0 h à 25 % et 0 h à 50 %', 'Prime de jeu 300,00 €', 'aucune ligne corrigée'],
    };
    expect(intituleDeVersion(entree)).toBe('Heures sup 0 h à 25 % et 0 h à 50 % · Prime de jeu 300,00 € · aucune ligne corrigée');
    expect(intituleDeVersion(entree)).not.toContain('retirée');
    expect(remplaceePar(entree)).toBe('Remplacée par : 1 prime retirée');
  });

  it('sans contenu lu, ne reprend pas le changement comme intitulé', () => {
    const entree = { changes_summary: '1 prime retirée', contenu: null };
    expect(intituleDeVersion(entree)).toBe('Contenu de cette version non lu.');
  });
});

describe('phrase de l’onglet', () => {
  it('cite les régularisations et les lignes corrigées', () => {
    expect(PHRASE_RESTAURATION).toContain('régularisations');
    expect(PHRASE_RESTAURATION).toContain('lignes corrigées');
  });
});
