import apiClient from '@/api/apiClient';

export interface ContractPeriod {
  id: string;
  employee_id: string;
  company_id: string;
  contract_type: string;
  date_debut: string;
  date_fin: string;
}

export async function listContractPeriods(employeeId: string): Promise<ContractPeriod[]> {
  const { data } = await apiClient.get<ContractPeriod[]>(
    `/api/employees/${employeeId}/contract-periods`,
  );
  return data;
}

export async function addContractPeriod(
  employeeId: string,
  body: { contract_type: string; date_debut: string; date_fin: string },
): Promise<ContractPeriod> {
  const { data } = await apiClient.post<ContractPeriod>(
    `/api/employees/${employeeId}/contract-periods`,
    body,
  );
  return data;
}

export async function deleteContractPeriod(employeeId: string, periodId: string): Promise<void> {
  await apiClient.delete(`/api/employees/${employeeId}/contract-periods/${periodId}`);
}

/** Ce que « Nouveau contrat » propose pour un salarié parti, ou pourquoi rien. */
export interface NewContractPreview {
  possible: boolean;
  raison: string | null;
  contrat_precedent: { contract_type: string; date_debut: string; date_fin: string } | null;
  premier_jour_possible: string | null;
  date_anciennete: string | null;
  prerempli: {
    contract_type: string;
    duree_hebdomadaire: number | null;
    salaire_mensuel: number | null;
    job_title: string | null;
  };
  types: string[];
}

export interface NewContractBody {
  date_debut: string;
  contract_type: string;
  date_fin: string | null;
  duree_hebdomadaire: number;
  salaire_mensuel: number;
  job_title: string | null;
  reprendre_anciennete: boolean;
}

export interface NewContractResult<E = unknown> {
  message: string;
  avertissements: string[];
  contrat_precedent: ContractPeriod;
  date_anciennete: string;
  employee: E;
}

export async function getNewContractPreview(employeeId: string): Promise<NewContractPreview> {
  const { data } = await apiClient.get<NewContractPreview>(
    `/api/employees/${employeeId}/new-contract`,
  );
  return data;
}

export async function createNewContract<E = unknown>(
  employeeId: string,
  body: NewContractBody,
): Promise<NewContractResult<E>> {
  const { data } = await apiClient.post<NewContractResult<E>>(
    `/api/employees/${employeeId}/new-contract`,
    body,
  );
  return data;
}
