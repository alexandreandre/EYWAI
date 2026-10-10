export const PHRASE_FORFAIT_JOURS_SANS_HEURES_SUP =
  'Au forfait jours, pas d’heures supplémentaires : le temps se compte en jours.';

/**
 * Modèles de semaine à proposer. Au forfait jours, seuls ceux qui comptent en
 * jours (chaque jour vaut 0 ou 1) ont un sens ; « 7 h/jour » n'en a pas.
 */
export function modelesSemaineProposes<T extends { template: Record<number, string | undefined> }>(
  modeles: T[],
  forfaitJours: boolean
): T[] {
  if (!forfaitJours) return modeles;
  return modeles.filter((m) =>
    Object.values(m.template).every((v) => v == null || v === '' || v === '0' || v === '1')
  );
}
