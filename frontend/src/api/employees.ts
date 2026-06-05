import apiClient from '@/api/apiClient';
import type { EmployeeListItem } from '@/hooks/queries/useEmployeesQuery';
import type { Employee } from '@/features/employee-detail/types';

export type EmployeeLite = {
  id: string;
  first_name: string;
  last_name: string;
};

export type EmployeeSummaryStatus = 'active' | 'all' | 'payroll';

export async function getEmployee(employeeId: string): Promise<Employee> {
  const { data } = await apiClient.get<Employee>(`/api/employees/${employeeId}`);
  return data;
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
