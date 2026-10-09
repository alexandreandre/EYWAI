/**
 * Liste de préparation du Mode Groupé : le compteur de la barre latérale ne
 * connaît pas le mois choisi dans la fenêtre. Pour les calendriers, le juge est
 * le contrôle avant paie du mois choisi (`periode_a_saisir` côté serveur), le
 * même que celui de la liste de contrôle du mois : les deux écrans disent la
 * même chose.
 */

import type { Lecture } from './listeControleMois';

export type CompteEtape =
  | { statut: 'ok'; compte: number }
  | { statut: 'chargement' }
  | { statut: 'erreur' };

export function compteEtapeCalendriers(
  compteBarreLaterale: number,
  calendriersDuMois: Lecture<readonly string[]> | undefined
): CompteEtape {
  if (!calendriersDuMois || calendriersDuMois.statut === 'indisponible') {
    return { statut: 'ok', compte: compteBarreLaterale };
  }
  if (calendriersDuMois.statut === 'ok') {
    return { statut: 'ok', compte: calendriersDuMois.valeur.length };
  }
  return { statut: calendriersDuMois.statut };
}
