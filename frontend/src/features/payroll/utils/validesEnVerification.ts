/**
 * Un bulletin validé dont une donnée a changé (le calendrier du mois suivant
 * posé, par exemple) : Martine le recalcule sans rien enregistrer, hors de la
 * requête, pour savoir si un montant change (lot 42). Le temps du calcul
 * (quelques secondes), le serveur le dit `a_verifier` : ni « À recalculer »,
 * ni à jour. L'écran se relit tout seul jusqu'au verdict : identique, rien ne
 * s'affiche ; différent, « À recalculer » avec ce qui change.
 */

import { estBulletinImporte } from './bulletinImporte';

/** Relecture tant qu'un verdict est attendu (un recalcul dure environ 6 s). */
const RELECTURE_MS = 5000;

export const INFOBULLE_EN_VERIFICATION =
  'Une donnée de ce bulletin validé a changé depuis sa validation. Martine le recalcule sans rien enregistrer pour savoir si un montant change : le résultat s’affiche dans quelques secondes.';

export const MESSAGE_EN_VERIFICATION =
  'Une donnée de ce bulletin a changé depuis sa validation. Martine le recalcule sans rien enregistrer pour savoir si un montant change ; le résultat s’affiche ici dans quelques secondes.';

type AvecVerification = { a_verifier?: boolean | null; origine?: string | null };

export function enVerification(payslip: AvecVerification | null | undefined): boolean {
  if (!payslip || estBulletinImporte(payslip)) return false;
  return payslip.a_verifier === true;
}

/** `refetchInterval` de la liste des bulletins : relue tant qu'un verdict est attendu. */
export function intervalleDeRelecture(
  lignes: readonly AvecVerification[] | null | undefined
): number | false {
  return (lignes ?? []).some((ligne) => enVerification(ligne)) ? RELECTURE_MS : false;
}

/**
 * Délai avant de relire l'écran du bulletin, ou null. Jamais pendant une
 * correction en cours : la relecture l'effacerait.
 */
export function delaiAvantRelecture(
  payslip: AvecVerification | null | undefined,
  correctionEnCours: boolean
): number | null {
  if (correctionEnCours || !enVerification(payslip)) return null;
  return RELECTURE_MS;
}
