import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export type EmployeeListItem = {
  id: string;
  first_name: string;
  last_name: string;
  job_title?: string | null;
  contract_type?: string | null;
  hire_date?: string | null;
  employment_status?: string | null;
  current_exit_id?: string | null;
};

export function useEmployeesQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.employees(companyId),
    queryFn: async () => {
      const res = await apiClient.get<EmployeeListItem[]>('/api/employees');
      return res.data ?? [];
    },
    enabled: enabled && Boolean(companyId),
  });
}
