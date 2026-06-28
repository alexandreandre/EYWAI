import apiClient from '@/api/apiClient';
import type { EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';
import type { Employee } from '@/features/employee-detail/types';

export type EmployeeLite = {
  id: string;
  first_name: string;
  last_name: string;
};

export type EmployeeSummaryStatus = 'active' | 'all' | 'payroll';

export type UpdateEmployeePayload = {
  first_name?: string;
  last_name?: string;
  collective_agreement_id?: string | null;
  email?: string;
  phone_number?: string | null;
  salary_payment_method?: 'virement' | 'cheque' | 'especes' | null;
  nir?: string;
  date_naissance?: string;
  lieu_naissance?: string;
  nationalite?: string;
  adresse?: {
    rue?: string;
    code_postal?: string;
    ville?: string;
    voie?: string;
  };
  coordonnees_bancaires?: {
    iban?: string;
    bic?: string;
  };
  salaire_de_base?: {
    valeur?: number;
    montant?: number;
  };
  contract_end_date?: string | null;
  date_debut_execution?: string | null;
  date_conclusion_contrat?: string | null;
  prior_service_months?: number | null;
  seniority_reference_date?: string | null;
  periode_essai?: Record<string, unknown> | null;
  hire_date?: string;
  job_title?: string;
  contract_type?: string;
  statut?: string;
  is_temps_partiel?: boolean;
  duree_hebdomadaire?: number;
  classification_conventionnelle?: {
    groupe_emploi?: string;
    classe_emploi?: number;
    coefficient?: number;
  };
  team_id?: string | null;
  time_tracking_id?: string | null;
  is_subject_to_residence_permit?: boolean;
  residence_permit_expiry_date?: string | null;
  residence_permit_type?: string | null;
  residence_permit_number?: string | null;
  specificites_paie?: {
    prelevement_a_la_source?: {
      is_personnalise?: boolean;
      taux?: number;
    };
    transport?: { abonnement_mensuel_total?: number; indemnite_mensuelle_nette?: number };
    titres_restaurant?: { beneficie?: boolean; nombre_par_mois?: number };
    mutuelle?: {
      adhesion?: boolean;
      mutuelle_type_ids?: string[];
      lignes_specifiques?: unknown[];
    };
    prevoyance?: {
      adhesion?: boolean;
      lignes_specifiques?: unknown[];
    };
    [key: string]: unknown;
  };
};

export type EmployeeDeletionImpact = {
  employee_id: string;
  employee_name: string;
  counts: Record<string, number>;
  summary_lines: string[];
  has_user_account: boolean;
  has_data: boolean;
};

export async function getEmployeeDeletionImpact(
  employeeId: string,
): Promise<EmployeeDeletionImpact> {
  const { data } = await apiClient.get<EmployeeDeletionImpact>(
    `/api/employees/${employeeId}/deletion-impact`,
  );
  return data;
}

export async function deleteEmployee(employeeId: string): Promise<void> {
  await apiClient.delete(`/api/employees/${employeeId}`);
}

export async function getEmployee(employeeId: string): Promise<Employee> {
  const { data } = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
  return data;
}

export async function updateEmployee(
  employeeId: string,
  payload: UpdateEmployeePayload,
): Promise<Employee> {
  const { data } = await apiClient.put<Employee>(`/api/employees/${employeeId}`, payload);
  return data;
}

export async function confirmTrialPeriod(employeeId: string): Promise<Employee> {
  const { data } = await apiClient.patch<Employee>(
    `/api/employees/${employeeId}/trial-period/confirm`,
  );
  return data;
}

export async function fetchEmployees(): Promise<Employee[]> {
  const { data } = await apiClient.get<Employee[]>('/api/employees');
  return data ?? [];
}

export async function uploadEmployeeContract(employeeId: string, file: File): Promise<string | null> {
  const formData = new FormData();
  formData.append('file', file, file.name || 'contrat.pdf');
  const { data } = await apiClient.post<{ url?: string | null }>(
    `/api/employees/${employeeId}/contract`,
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
  return data.url ?? null;
}

export async function fetchEmployeesSummary(
  status: EmployeeSummaryStatus = 'all',
): Promise<EmployeeListItem[]> {
  const params =
    status === 'active'
      ? { status: 'active' }
      : status === 'payroll'
        ? { status: 'payroll' }
        : undefined;
  const { data } = await apiClient.get<EmployeeListItem[]>('/api/employees/summary', {
    params,
  });
  return data ?? [];
}

/** Liste minimale (sélecteurs) — utilise l’endpoint summary. */
export const getEmployeesLite = async (): Promise<EmployeeLite[]> => {
  const rows = await fetchEmployeesSummary('all');
  return rows.map((e) => ({
    id: e.id,
    first_name: e.first_name,
    last_name: e.last_name,
  }));
};

export type EmployeeFormationSelect = EmployeeLite & {
  email?: string | null;
};

/** Sélecteurs Formation (email pour résolution collaborateur non-RH). */
export async function getEmployeesForFormationSelect(): Promise<EmployeeFormationSelect[]> {
  const rows = await fetchEmployees();
  return rows.map((e) => ({
    id: e.id,
    first_name: e.first_name,
    last_name: e.last_name,
    email: e.email ?? null,
  }));
}
