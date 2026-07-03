/**
 * Constantes pour les types de contrat et statuts d'employés
 * 
 * IMPORTANT : le forfait jours est un réglage dédié (`is_forfait_jour`),
 * séparé du statut catégoriel affiché (`Cadre` / `Non-Cadre`).
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
 * Le forfait jours ne pollue pas cette liste : il se règle via un champ séparé.
 */
export const EMPLOYEE_STATUSES = [
  'Non-Cadre',
  'Cadre',
] as const;

/**
 * Types TypeScript dérivés des constantes
 */
export type ContractType = typeof CONTRACT_TYPES[number];
export type EmployeeStatus = typeof EMPLOYEE_STATUSES[number];

/**
 * Fonction utilitaire pour vérifier si un salarié est au forfait jours.
 */
export function isForfaitJour(
  status: string | null | undefined,
  explicit?: boolean | null,
): boolean {
  if (explicit !== undefined && explicit !== null) return Boolean(explicit);
  if (!status) return false;
  return status.toLowerCase().includes('forfait jour');
}

export const DEFAULT_CONTRACT_TYPE: ContractType = 'CDI';
export const DEFAULT_EMPLOYEE_STATUT: EmployeeStatus = 'Non-Cadre';

/** Valeurs affichées sur les offres recrutement (plus larges que la fiche paie). */
export const RECRUITMENT_JOB_CONTRACT_TYPES = [
  ...CONTRACT_TYPES,
  'Freelance',
  'Autre',
] as const;

export type EmployeeContractConfigValues = {
  contract_type: string;
  statut: string;
  is_forfait_jour?: boolean;
  contract_end_date?: string;
  date_debut_execution?: string;
  date_conclusion_contrat?: string;
  maintien_regime_apprenti?: boolean;
};

export const EMPTY_EMPLOYEE_CONTRACT_CONFIG: EmployeeContractConfigValues = {
  contract_type: DEFAULT_CONTRACT_TYPE,
  statut: DEFAULT_EMPLOYEE_STATUT,
  is_forfait_jour: false,
  contract_end_date: '',
  date_debut_execution: '',
  date_conclusion_contrat: '',
  maintien_regime_apprenti: false,
};

/** Harmonise les libellés hétérogènes (offres, anciennes fiches) vers CONTRACT_TYPES. */
export function normalizeContractType(value: string | null | undefined): string {
  const raw = (value ?? '').trim();
  if (!raw) return DEFAULT_CONTRACT_TYPE;

  const exact = CONTRACT_TYPES.find((t) => t.toLowerCase() === raw.toLowerCase());
  if (exact) return exact;

  const v = raw.toLowerCase();
  if (v === 'alternance' || v.includes("contrat d'alternance") || v.includes('contrat alternance')) {
    return 'Apprentissage';
  }
  if (v.includes('convention de stage') || v === 'convention stage') return 'Stage';
  if (v.includes('apprentissage')) return 'Apprentissage';
  if (v.includes('professionnalisation')) return 'Contrat de professionnalisation';
  if (v.includes('stage')) return 'Stage';
  if (v.includes('intérim') || v.includes('interim')) return 'Intérim';
  if (v.includes('portage')) return 'Portage salarial';
  if (v.includes('cdd') && !v.includes('cdi')) return 'CDD';
  if (v.includes('cdi')) return 'CDI';

  return raw;
}

export function isApprentissageContract(contractType: string | null | undefined): boolean {
  return (contractType ?? '').toLowerCase().includes('apprentissage');
}

export function isAlternanceContract(contractType: string | null | undefined): boolean {
  const t = (contractType ?? '').toLowerCase();
  return t.includes('apprentissage') || t.includes('professionnalisation');
}

export function isStageContract(contractType: string | null | undefined): boolean {
  return (contractType ?? '').toLowerCase().includes('stage');
}

export function isCddContract(contractType: string | null | undefined): boolean {
  const t = (contractType ?? '').toLowerCase();
  return t.includes('cdd') && !t.includes('cdi');
}

export function needsContractEndDate(contractType: string | null | undefined): boolean {
  return isCddContract(contractType) || isStageContract(contractType);
}

export function validateEmployeeContractConfig(
  values: Pick<
    EmployeeContractConfigValues,
    'contract_type' | 'contract_end_date'
  >,
): string | null {
  if (needsContractEndDate(values.contract_type) && !values.contract_end_date?.trim()) {
    return 'La date de fin de contrat est requise pour un CDD ou un stage.';
  }
  return null;
}
