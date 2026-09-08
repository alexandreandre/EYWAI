/**
 * Lecture humaine de la fenêtre des variables (heures sup, paniers).
 *
 * La gestionnaire de paie raisonne en semaines : « S26 à S30 », pas en dates
 * ISO. Ces fonctions traduisent ce que renvoie l'API pour l'affichage, et
 * disent si la société est restée au mois civil (MAJI, ZONE 404) — auquel cas
 * il n'y a rien à arrêter.
 */

import type { PeriodeVariables } from '@/api/periodeVariables';

/** `2026-07-26` → `26/07/2026`. */
export const formatFr = (iso: string): string => {
  const [annee, mois, jour] = iso.split('-');
  return `${jour}/${mois}/${annee}`;
};

/** `[26, 27, 28, 29, 30]` → `semaines 26 à 30`. */
export const libelleSemaines = (semaines: number[]): string => {
  if (semaines.length === 0) return '';
  if (semaines.length === 1) return `semaine ${semaines[0]}`;
  return `semaines ${semaines[0]} à ${semaines[semaines.length - 1]}`;
};

/** Vrai quand la fenêtre est le mois civil : rien à décaler, rien à saisir. */
export const estSurLeMoisCivil = (fenetre: PeriodeVariables): boolean =>
  fenetre.debut === fenetre.mois_civil[0] && fenetre.fin === fenetre.mois_civil[1];
