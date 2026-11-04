/**
 * Compte comptable propre à un prêt : celui que la comptabilité ouvre pour ce
 * prêt (ex. 42511000). Dans l'OD de paie, chaque remboursement le solde ; vide,
 * le prêt suit le compte « prêt » de la société. Même règle que le serveur :
 * 3 à 20 chiffres, espaces retirés.
 */
export const COMPTE_DU_PRET_MAX = 20;

export const MESSAGE_COMPTE_DU_PRET = `Des chiffres seulement, de 3 à ${COMPTE_DU_PRET_MAX} (ex. 42511000), ou la case vide pour le compte de la société.`;

export function compteDuPretSaisi(texte: string | null | undefined): {
  compte: string | null;
  erreur: string | null;
} {
  const compte = (texte ?? '').replace(/\s/g, '');
  if (!compte) return { compte: null, erreur: null };
  if (!/^[0-9]+$/.test(compte) || compte.length < 3 || compte.length > COMPTE_DU_PRET_MAX) {
    return { compte: null, erreur: MESSAGE_COMPTE_DU_PRET };
  }
  return { compte, erreur: null };
}
