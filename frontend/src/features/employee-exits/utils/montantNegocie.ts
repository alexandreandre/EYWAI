/**
 * Montant de la convention de rupture, tapé sur le départ.
 * Vide : le minimum légal calculé s'applique (valeur null).
 */
export type LectureMontantNegocie = { valeur: number | null } | { erreur: string };

const ERREUR = 'Saisissez un montant positif, par exemple 12 500,00.';

export function lireMontantNegocie(saisie: string): LectureMontantNegocie {
  const texte = saisie.replace(/[\s\u00a0\u202f€]/g, '').replace(',', '.');
  if (texte === '') return { valeur: null };
  if (!/^\d+(\.\d{1,2})?$/.test(texte)) return { erreur: ERREUR };
  return { valeur: Number(texte) };
}
