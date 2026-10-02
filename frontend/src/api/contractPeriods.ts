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
