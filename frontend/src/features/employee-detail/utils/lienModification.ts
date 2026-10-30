/**
 * Lien vers la fiche d'un salarié, formulaire de modification ouvert : la
 * revue pré-paie y envoie quand une rubrique de la DSN manque à la fiche.
 */
const PARAMETRE = 'modifier';
const VALEUR = 'fiche';

export function lienModifierFiche(employeeId: string): string {
  return `/employees/${encodeURIComponent(employeeId)}?${PARAMETRE}=${VALEUR}`;
}

export function ouvreLaModification(search: string): boolean {
  return new URLSearchParams(search).get(PARAMETRE) === VALEUR;
}
