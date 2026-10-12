/**
 * L'aide sous les lignes de prévoyance, quand aucune n'est saisie.
 *
 * Non-cadre : le moteur applique le barème national. Cadre : il ne pose que les
 * lignes de la fiche, donc rien sans elles ([B4], 12/10/2026).
 */
export function aideLignesPrevoyance(cadre: boolean, nbLignes: number): string | null {
  if (nbLignes > 0) return null;
  return cadre
    ? 'Saisissez les lignes du contrat de prévoyance : sans ligne, le bulletin d’un cadre ne porte aucune cotisation de prévoyance.'
    : 'Sans ligne saisie, le barème national s’applique au bulletin.';
}
