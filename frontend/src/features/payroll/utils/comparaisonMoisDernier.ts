/**
 * Section « Ce qui a changé par rapport au mois dernier ».
 *
 * Le front n'invente aucun montant : il affiche le texte fourni par le serveur,
 * ou « Pas de bulletin le mois dernier ».
 */

export const TEXTE_PAS_DE_BULLETIN = 'Pas de bulletin le mois dernier';

export type PaireMontant = {
  avant: number;
  apres: number;
};

export type ComparaisonMoisDernier = {
  present?: boolean;
  texte?: string | null;
  brut?: PaireMontant | null;
  net?: PaireMontant | null;
  heures_sup?: PaireMontant | null;
  absences?: PaireMontant | null;
};

export function messageComparaisonMoisDernier(
  comparaison: ComparaisonMoisDernier | null | undefined
): string {
  if (!comparaison || comparaison.present === false) {
    return TEXTE_PAS_DE_BULLETIN;
  }
  const texte = typeof comparaison.texte === 'string' ? comparaison.texte.trim() : '';
  return texte.length > 0 ? texte : TEXTE_PAS_DE_BULLETIN;
}
