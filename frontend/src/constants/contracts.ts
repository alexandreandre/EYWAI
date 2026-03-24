/**
 * Constantes pour les types de contrat et statuts d'employés
 * 
 * IMPORTANT : Le forfait jour est déterminé par le STATUT de l'employé,
 * et non par le type de contrat. Un employé peut avoir un contrat CDI
 * avec le statut "Cadre au forfait jour", ce qui signifie qu'il travaille
 * en forfait jour (gestion par jours travaillés 0/1) plutôt qu'en heures.
 */

/**
 * Liste des types de contrat disponibles
 */
export const CONTRACT_TYPES = [
  'CDI',
  'CDD',
  'Intérim',
  'Apprentissage',
  'Contrat de professionnalisation',
  'Stage',
  'Portage salarial',
] as const;

/**
 * Liste des statuts d'employés disponibles
 * 
 * Note : Les statuts contenant "forfait jour" déterminent que l'employé
 * travaille en forfait jour (gestion par jours travaillés 0/1) plutôt
 * qu'en heures dans le calendrier.
 */
export const EMPLOYEE_STATUSES = [
  'Non-Cadre',
  'Cadre',
  'Cadre au forfait jour',
  'Non-Cadre au forfait jour',
] as const;

/**
 * Types TypeScript dérivés des constantes
 */
export type ContractType = typeof CONTRACT_TYPES[number];
export type EmployeeStatus = typeof EMPLOYEE_STATUSES[number];

/**
 * Fonction utilitaire pour vérifier si un statut correspond à un forfait jour
 */
export function isForfaitJour(status: string | null | undefined): boolean {
  if (!status) return false;
  return status.includes('forfait jour');
}
