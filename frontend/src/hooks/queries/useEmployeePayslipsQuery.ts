import { useQuery } from '@tanstack/react-query';
import { getEmployeePayslips } from '@/api/payslips';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export function useEmployeePayslipsQuery(employeeId: string | undefined) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.employeePayslips(companyId, employeeId),
    queryFn: () => getEmployeePayslips(employeeId!),
    enabled: Boolean(companyId && employeeId),
    placeholderData: (previous) => previous,
  });
}
