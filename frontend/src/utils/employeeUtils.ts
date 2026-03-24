/**
 * Utilitaires pour la gestion des employés
 */

/**
 * Vérifie si un statut d'employé correspond à un forfait jour
 * 
 * Le forfait jour est déterminé par le statut de l'employé (ex: "Cadre au forfait jour").
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
export function isForfaitJour(statut: string | null | undefined): boolean {
  if (!statut) return false;
  
  // Vérification insensible à la casse
  return statut.toLowerCase().includes('forfait jour');
}
