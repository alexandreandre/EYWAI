/**
 * Lecture humaine de la fenêtre des variables (heures sup, paniers).
 *
 * La gestionnaire de paie raisonne en semaines : « S26 à S30 », pas en dates
 * ISO. Ces fonctions traduisent ce que renvoie l'API pour l'affichage, et
 * disent si la société est restée au mois civil (MAJI, ZONE 404) — auquel cas
 * il n'y a rien à arrêter.
 */

import type { PeriodeVariables } from '@/api/periodeVariables';
import { getUserErrorMessage } from '@/lib/errorMessages';

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

const MOIS_EN_CLAIR = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** « 26 juillet 2026 » depuis une date ISO (jour 1 : « 1er »). */
export function dateEnClair(iso: string): string {
  const [annee, mois, jour] = iso.split('-').map(Number);
  if (!annee || !mois || !jour) return iso;
  return `${jour === 1 ? '1er' : jour} ${MOIS_EN_CLAIR[mois - 1]} ${annee}`;
}

/** Toast après « Appliquer » : la date retenue, et ce qui part sur le mois suivant. */
export function confirmationFenetre(finIso: string): { title: string; description: string } {
  return {
    title: 'Fenêtre des variables enregistrée',
    description: `Les variables s’arrêtent le ${dateEnClair(finIso)}. Ce qui suit partira sur le mois suivant.`,
  };
}

export function messageEchecFenetre(erreur: unknown): string {
  return getUserErrorMessage(
    erreur,
    'La fenêtre n’a pas été enregistrée. Vérifiez la date d’arrêt choisie, puis réessayez.',
  );
}
