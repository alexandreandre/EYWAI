/**
 * API « saisies » = primes et monthly-inputs (éléments variables de paie).
 * Ne pas confondre avec `saisiesAvances.ts` (saisies sur salaire + avances sur salaire).
 */
import apiClient from './apiClient';
import { enTeteSociete } from './payslips';


// --- INTERFACES ---
export interface PrimeFromCatalogue {
  id: string;
  libelle: string;
  soumise_a_cotisations: boolean;
  soumise_a_impot: boolean;
}

export interface MonthlyInput {
  id: string;
  employee_id: string;
  year: number;
  month: number;
  name: string;
  description?: string;
  amount: number;
  is_socially_taxed: boolean;
  is_taxable: boolean;
  /** Vrai : seul le net à payer bouge (retenue si négatif, versement si positif). */
  sur_le_net?: boolean;
  /** Id catalogue (ex. "prime_partage_valeur") — déclenche les traitements dédiés du moteur (PPV…). */
  catalog_prime_id?: string | null;
  created_at: string;
  updated_at: string;
}

export type MonthlyInputCreate = Omit<MonthlyInput, 'id' | 'created_at' | 'updated_at'>;

// --- FONCTIONS D'API ---

export const getPrimesCatalogue = () => {
  return apiClient.get<PrimeFromCatalogue[]>('/api/primes-catalogue');
};

/**
 * `bulletins_a_recalculer` : les bulletins du mois que l'écriture rend « À recalculer »
 * (vide : aucun bulletin ; null : le serveur n'a pas pu le chercher).
 */
export interface BulletinsARecalculer {
  bulletins_a_recalculer?: { employee_id: string; year: number; month: number }[] | null;
}

export const createMonthlyInputs = (data: MonthlyInputCreate[]) => {
  return apiClient.post<{ status: string; inserted: number } & BulletinsARecalculer>('/api/monthly-inputs', data);
};


export const getAllMonthlyInputs = (year: number, month: number) => {
  return apiClient.get<MonthlyInput[]>('/api/monthly-inputs', { params: { year, month } });
};




/**
 * Supprime une saisie. Une prime d'une règle automatique n'est pas supprimée
 * (la préparation du mois la recréerait) : elle passe à 0 €, `retiree` vaut vrai.
 */
export const deleteMonthlyInput = (id: string) => {
  return apiClient.delete<{ status: string; retiree?: boolean } & BulletinsARecalculer>(`/api/monthly-inputs/${id}`);
};

/**
 * Corrige une saisie. La ligne devient prioritaire sur la génération mensuelle :
 * « Préparer variables du mois » ne l'écrasera plus.
 */
export const updateMonthlyInput = (
  id: string,
  data: Partial<
    Pick<MonthlyInput, 'amount' | 'name' | 'description' | 'is_socially_taxed' | 'is_taxable'>
  >,
  companyId?: string | null,
) => {
  return apiClient.patch<MonthlyInput & BulletinsARecalculer>(`/api/monthly-inputs/${id}`, data, enTeteSociete(companyId));
};

/** Une saisie pour un salarié, dans la société donnée (sinon la société active). */
export const createEmployeeMonthlyInput = (
  employeeId: string,
  data: Omit<MonthlyInputCreate, 'employee_id'>,
  companyId?: string | null,
) => {
  return apiClient.post<MonthlyInput>(
    `/api/employees/${employeeId}/monthly-inputs`,
    data,
    enTeteSociete(companyId),
  );
};

export const getEmployeeMonthlyInputs = (employeeId: string, year: number, month: number) => {
  return apiClient.get(`/api/employees/${employeeId}/monthly-inputs`, {
    params: { year, month },
  });
};

export const deleteEmployeeMonthlyInput = (
  employeeId: string,
  inputId: string,
  companyId?: string | null,
) => {
  return apiClient.delete(
    `/api/employees/${employeeId}/monthly-inputs/${inputId}`,
    enTeteSociete(companyId),
  );
};


