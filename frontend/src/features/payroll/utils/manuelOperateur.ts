/**
 * Texte du manuel opérateur (mode paie). Pas de nom de salarié, pas de
 * société réelle : Alexandre relit avant mise en ligne.
 *
 * Le texte vit dans `manuelOperateur.json`, seule source : l’assistant IA en
 * lit une copie identique (backend/app/modules/copilot/infrastructure/
 * manuel_paie.json), et un test backend refuse qu’elles divergent. Après une
 * modification ici, recopiez le fichier vers le backend.
 */

import manuel from './manuelOperateur.json';

export type EtapeManuel = {
  titre: string;
  paragraphes: string[];
};

export type PiegeManuel = {
  titre: string;
  quoiFaire: string;
};

export type SectionManuel = { id: string; titre: string; intro?: string };

export const SECTIONS_MANUEL: SectionManuel[] = manuel.sections;

export const ETAPES_MANUEL: EtapeManuel[] = manuel.etapes;

export const PIEGES_MANUEL: PiegeManuel[] = manuel.pieges;

export function titresDesEtapes(): string[] {
  return ETAPES_MANUEL.map((e) => e.titre);
}

export function TEXTE_MANUEL(): string {
  const etapes = ETAPES_MANUEL.flatMap((e) => [e.titre, ...e.paragraphes]);
  const pieges = PIEGES_MANUEL.flatMap((p) => [p.titre, p.quoiFaire]);
  const sections = SECTIONS_MANUEL.flatMap((s) => [s.titre, s.intro ?? '']);
  return [...sections, ...etapes, ...pieges].join('\n');
}
