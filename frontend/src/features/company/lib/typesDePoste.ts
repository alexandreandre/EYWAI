/**
 * Types de poste du planning d'équipes (lot C, 24/11).
 *
 * Un type appartient à la société, ou à la convention du planning (partagé avec
 * les autres sociétés de cette convention). Modifier un type de convention crée
 * une copie propre à la société : le type partagé n'est jamais réécrit.
 */

export type OrigineTypeDePoste = 'societe' | 'convention';

export function estTypeDeConvention(st: { origine?: OrigineTypeDePoste }): boolean {
  return st.origine === 'convention';
}

export function libelleConventionPlanning(cc: { label: string; idcc?: string | null }): string {
  return cc.idcc ? `${cc.label} (IDCC ${cc.idcc})` : cc.label;
}

export function messageListeVide(): string {
  return 'Aucun type de poste. Ajoutez-en un ci-dessous ou appliquez un modèle 3×8.';
}

/** Titre du message d'échec, par action (jamais un « L'action n'a pas abouti » muet). */
export const TITRE_ECHEC_PLANNING = {
  parametres: 'Paramètres du planning non enregistrés',
  creation: 'Type de poste non créé',
  modification: 'Type de poste non enregistré',
  desactivation: 'Type de poste non désactivé',
  modele: 'Modèle 3×8 non appliqué',
} as const;
