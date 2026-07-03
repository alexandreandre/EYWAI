/**
 * Utilitaires pour la gestion des employés
 */

/**
 * Vérifie si un statut d'employé correspond à un forfait jour
 * 
 * Le forfait jours est désormais un champ dédié (`is_forfait_jour`).
 * Le statut historique contenant "forfait jour" reste supporté en lecture.
 * Les employés en forfait jour gèrent leur temps de travail par jours travaillés (0/1)
 * plutôt que par heures dans le calendrier.
 * 
 * @param statut - Le statut de l'employé à vérifier
 * @returns true si le statut contient "forfait jour" (insensible à la casse), false sinon
 * 
 * @example
 * isForfaitJour("Cadre au forfait jour") // true
 * isForfaitJour("Non-Cadre") // false
 * isForfaitJour("CADRE AU FORFAIT JOUR") // true (insensible à la casse)
 * isForfaitJour(null) // false
 * isForfaitJour(undefined) // false
 */
export function isForfaitJour(
  statut: string | null | undefined,
  explicit?: boolean | null,
): boolean {
  if (explicit !== undefined && explicit !== null) return Boolean(explicit);
  if (!statut) return false;
  return statut.toLowerCase().includes('forfait jour');
}
