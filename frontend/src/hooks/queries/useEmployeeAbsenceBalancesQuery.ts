import { useQuery } from '@tanstack/react-query';
import { getEmployeeAbsenceBalances } from '@/api/absences';
import { useCompany } from '@/contexts/CompanyContext';
import { queryKeys } from '@/lib/queryKeys';

export function useEmployeeAbsenceBalancesQuery(employeeId: string | undefined) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id;

  return useQuery({
    queryKey: queryKeys.employeeAbsenceBalances(companyId, employeeId),
    queryFn: async () => {
      const res = await getEmployeeAbsenceBalances(employeeId!);
      return res.data.balances;
    },
    enabled: Boolean(companyId && employeeId),
  });
}
