import { useQuery } from '@tanstack/react-query';
import { fetchEmployeesSummary } from '@/api/employees';
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
  duree_hebdomadaire?: number | null;
};

export function useEmployeesQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.employees(companyId),
    queryFn: () => fetchEmployeesSummary('all'),
    enabled: enabled && Boolean(companyId),
    placeholderData: (previous) => previous,
  });
}
