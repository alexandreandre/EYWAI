/**
 * API « saisies » = primes et monthly-inputs (éléments variables de paie).
 * Ne pas confondre avec `saisiesAvances.ts` (saisies sur salaire + avances sur salaire).
 */
import apiClient from './apiClient';


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
  created_at: string;
  updated_at: string;
}

export type MonthlyInputCreate = Omit<MonthlyInput, 'id' | 'created_at' | 'updated_at'>;

// --- FONCTIONS D'API ---

export const getPrimesCatalogue = () => {
  return apiClient.get<PrimeFromCatalogue[]>('/api/primes-catalogue');
};

export const createMonthlyInputs = (data: MonthlyInputCreate[]) => {
  return apiClient.post('/api/monthly-inputs', data);
};


export const getAllMonthlyInputs = (year: number, month: number) => {
  return apiClient.get<MonthlyInput[]>('/api/monthly-inputs', { params: { year, month } });
};




export const deleteMonthlyInput = (id: string) => {
  return apiClient.delete(`/api/monthly-inputs/${id}`);
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
) => {
  return apiClient.patch<MonthlyInput>(`/api/monthly-inputs/${id}`, data);
};

export const getEmployeeMonthlyInputs = (employeeId: string, year: number, month: number) => {
  return apiClient.get(`/api/employees/${employeeId}/monthly-inputs`, {
    params: { year, month },
  });
};

export const deleteEmployeeMonthlyInput = (employeeId: string, inputId: string) => {
  return apiClient.delete(`/api/employees/${employeeId}/monthly-inputs/${inputId}`);
};


