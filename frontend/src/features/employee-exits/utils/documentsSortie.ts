/**
 * Les documents de sortie (solde, attestation, certificat) reprennent les
 * sommes du bulletin du mois de sortie. Tant qu'il n'existe pas, on ne les
 * génère pas : l'écran le dit et les boutons restent grisés.
 */

export const MESSAGE_GENERER_DABORD_BULLETIN =
  "Générez d'abord le bulletin de sortie";

export function documentsDeSortieGrises(
  bulletinDeSortie: { mois?: string } | null | undefined
): boolean {
  return bulletinDeSortie == null;
}
