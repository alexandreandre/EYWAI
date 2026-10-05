import { readdirSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

import {
  PIEGES_MANUEL,
  SECTIONS_MANUEL,
  TEXTE_MANUEL,
  titresDesEtapes,
} from './manuelOperateur';

/** Tout le code de l’écran, hors tests et hors manuel lui-même. */
function codeDeLEcran(): string {
  const racine = fileURLToPath(new URL('../../..', import.meta.url));
  const fichiers: string[] = [];
  const parcourir = (dossier: string) => {
    for (const entree of readdirSync(dossier, { withFileTypes: true })) {
      const chemin = path.join(dossier, entree.name);
      if (entree.isDirectory()) parcourir(chemin);
      else if (/\.tsx?$/.test(entree.name) && !/\.test\.tsx?$/.test(entree.name)
        && !entree.name.startsWith('manuelOperateur')) {
        fichiers.push(chemin);
      }
    }
  };
  parcourir(racine);
  return fichiers.map((f) => readFileSync(f, 'utf-8')).join('\n');
}

const apostrophes = (s: string) => s.replace(/&apos;|’/g, "'");

describe('manuel opérateur', () => {
  it('décrit la paie du mois étape par étape', () => {
    const titres = titresDesEtapes().join(' ').toLowerCase();
    for (const mot of [
      'pointage',
      'calendrier',
      'absence',
      'générer',
      'vérifier',
      'corriger',
      'recalculer',
      'valider',
      'sortie',
      'comptabilité',
      'banque',
      'dsn',
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

  it('couvre ce pour quoi la gestionnaire appelait le développeur', () => {
    const texte = TEXTE_MANUEL();
    for (const attendu of [
      // Exports comptable et banque.
      'Envois',
      'Envoyer vers compta',
      'Envoyer vers banque',
      'Marquer comme transmis',
      'Exports à refaire',
      // DSN : l’état réel et quoi faire en attendant.
      'Déclarations',
      'DSN mensuelle',
      'pas encore déposable',
      'ancien logiciel',
      // Corriger par les variables du mois, puis recalculer.
      'Primes du mois',
      'Enregistrer et recalculer',
      // Bulletin déjà validé.
      'Corriger et repasser en brouillon',
      'Correction verrouillée',
      // Pointages, y compris un fichier déjà importé.
      'Importer des pointages',
      'Refaire l’import de ce fichier',
      // Solde de congés, sans promettre plus que l’écran.
      'Soldes congés',
      // Génération en échec : le ticket et ce qu’il faut y mettre.
      'Échec',
      'Support',
      'Bulletin non généré',
      'message exact',
    ]) {
      expect(texte, attendu).toContain(attendu);
    }
  });

  it('ne cite que des libellés qui existent à l’écran', () => {
    const code = apostrophes(codeDeLEcran());
    const cites = [...TEXTE_MANUEL().matchAll(/«\s*([^»]+?)\s*»/g)].map((m) => m[1]);
    expect(cites.length).toBeGreaterThan(20);
    const absents = cites.filter((libelle) => !code.includes(apostrophes(libelle)));
    expect(absents).toEqual([]);
  });

  it('n’cite aucune société réelle ni un nom de salarié', () => {
    const brut = TEXTE_MANUEL().toLowerCase();
    expect(brut).not.toMatch(/colorplast|comitech|cartol|lewis/);
    expect(SECTIONS_MANUEL.length).toBeGreaterThan(1);
  });
});
