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
    // Pas de placeholderData : au changement de salarié, on montre un état de
    // chargement plutôt que les bulletins du salarié précédent.
  });
}
