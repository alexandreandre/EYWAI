import { describe, expect, it } from 'vitest';

import {
  PIEGES_MANUEL,
  SECTIONS_MANUEL,
  TEXTE_MANUEL,
  titresDesEtapes,
} from './manuelOperateur';

describe('manuel opérateur', () => {
  it('décrit la paie du mois étape par étape', () => {
    const titres = titresDesEtapes().join(' ').toLowerCase();
    for (const mot of [
      'pointage',
      'calendrier',
      'absence',
      'générer',
      'vérifier',
      'recalculer',
      'valider',
      'sortie',
    ]) {
      expect(titres, mot).toContain(mot);
    }
  });

  it('explique les pièges déjà corrigés et quoi faire', () => {
    const textes = PIEGES_MANUEL.map((p) => `${p.titre} ${p.quoiFaire}`).join(' ').toLowerCase();
    expect(textes).toMatch(/arrêt/);
    expect(textes).toMatch(/heure/);
    expect(textes).toMatch(/périmé|recharg/);
    expect(textes).toMatch(/recalcul/);
    expect(textes).toMatch(/négatif/);
    expect(textes).toMatch(/départ|sortie/);
    expect(textes).toMatch(/rib/);
    for (const piege of PIEGES_MANUEL) {
      expect(piege.quoiFaire.length).toBeGreaterThan(20);
    }
  });

  it('n’cite aucune société réelle ni un nom de salarié', () => {
    const brut = TEXTE_MANUEL().toLowerCase();
    expect(brut).not.toMatch(/colorplast|comitech|cartol|lewis/);
    expect(SECTIONS_MANUEL.length).toBeGreaterThan(1);
  });
});
