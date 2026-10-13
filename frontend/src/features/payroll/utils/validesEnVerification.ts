/**
 * Un bulletin validé dont une donnée a changé (le calendrier du mois suivant
 * posé, par exemple) : Martine le recalcule sans rien enregistrer, hors de la
 * requête, pour savoir si un montant change (lot 42). Le temps du calcul
 * (quelques secondes), le serveur le dit `a_verifier` : ni « À recalculer »,
 * ni à jour. L'écran se relit tout seul jusqu'au verdict : identique, rien ne
 * s'affiche ; différent, « À recalculer » avec ce qui change.
 *
 * Lot 43 : un brouillon l'est aussi, quand seul le planning d'à côté a changé
 * (mois suivant posé, semaine à cheval). Ses textes ne parlent pas de validation.
 */

import { estBulletinImporte } from './bulletinImporte';

/** Relecture tant qu'un verdict est attendu (un recalcul dure environ 6 s). */
const RELECTURE_MS = 5000;

export const INFOBULLE_EN_VERIFICATION =
  'Une donnée de ce bulletin validé a changé depuis sa validation. Martine le recalcule sans rien enregistrer pour savoir si un montant change : le résultat s’affiche dans quelques secondes.';

export const MESSAGE_EN_VERIFICATION =
  'Une donnée de ce bulletin a changé depuis sa validation. Martine le recalcule sans rien enregistrer pour savoir si un montant change ; le résultat s’affiche ici dans quelques secondes.';

/** Brouillon : seul le planning a pu changer pour qu'il soit vérifié ainsi. */
const INFOBULLE_BROUILLON_EN_VERIFICATION =
  'Le planning a changé depuis le calcul de ce bulletin. Martine le recalcule sans rien enregistrer pour savoir si un montant change : le résultat s’affiche dans quelques secondes.';

const MESSAGE_BROUILLON_EN_VERIFICATION =
  'Le planning a changé depuis le calcul de ce bulletin. Martine le recalcule sans rien enregistrer pour savoir si un montant change ; le résultat s’affiche ici dans quelques secondes.';

type AvecStatut = { status?: string | null } | null | undefined;

/** L'info-bulle de « Vérification… » : celle d'un validé, ou celle d'un brouillon. */
export function infobulleEnVerification(payslip: AvecStatut): string {
  return payslip?.status === 'valide' ? INFOBULLE_EN_VERIFICATION : INFOBULLE_BROUILLON_EN_VERIFICATION;
}

/** Le bandeau « Vérification en cours » de l'écran du bulletin. */
export function messageEnVerification(payslip: AvecStatut): string {
  return payslip?.status === 'valide' ? MESSAGE_EN_VERIFICATION : MESSAGE_BROUILLON_EN_VERIFICATION;
}

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
