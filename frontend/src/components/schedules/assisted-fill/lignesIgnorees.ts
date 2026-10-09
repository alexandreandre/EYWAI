/**
 * Lignes d'une revue d'import que « Enregistrer » n'écrira pas.
 *
 * Une ligne qui porte des heures sans être enregistrable (salarié non associé,
 * ligne à vérifier) était écartée sans un mot : au réimport, les jours du
 * salarié n'étaient pas réécrits et rien ne le disait. L'écran les nomme avant
 * l'enregistrement, et le résultat aussi.
 */
import { rowCarriesHours } from './reviewRowRules';

export interface LigneARaisonner {
  rawName: string;
  employeeId: string | null;
  days: { heures: number | null; type: string }[];
  enregistrable: boolean;
}

export interface LigneIgnoree {
  nom: string;
  raison: string;
}

/** Les lignes avec des heures (ou une absence) que l'enregistrement laissera de côté. */
export function lignesIgnorees(rows: LigneARaisonner[]): LigneIgnoree[] {
  return rows
    .filter((r) => !r.enregistrable && rowCarriesHours(r))
    .map((r) => ({
      nom: r.rawName,
      raison: r.employeeId
        ? 'à vérifier (cochez « Inclure écarts / match douteux »)'
        : 'aucun salarié associé',
    }));
}

const liste = (l: LigneIgnoree[]) => l.map((x) => `« ${x.nom} » (${x.raison})`).join(', ');

/** Phrase affichée avant l'enregistrement ; null quand toutes les lignes sont prises. */
export function phraseLignesIgnorees(l: LigneIgnoree[]): string | null {
  if (l.length === 0) return null;
  const debut = l.length === 1 ? '1 ligne ne sera pas enregistrée' : `${l.length} lignes ne seront pas enregistrées`;
  return `${debut} : ${liste(l)}.`;
}

/** Fin de la description du résultat : les lignes qui n'ont pas été enregistrées. */
export function suiteResultatLignesIgnorees(l: LigneIgnoree[]): string {
  return l.length === 0 ? '' : ` Non enregistré : ${liste(l)}.`;
}
