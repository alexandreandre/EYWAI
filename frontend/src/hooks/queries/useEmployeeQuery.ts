import { useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getEmployee } from '@/api/employees';
import { queryKeys } from '@/lib/queryKeys';
import type { Employee } from '@/features/employee-detail/types';
import { useActiveCompanyId } from './useCompanyId';

export function useEmployeeQuery(
  employeeId: string | undefined,
  options?: { placeholder?: Employee },
) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.employee(companyId, employeeId),
    queryFn: () => getEmployee(employeeId!),
    enabled: Boolean(companyId && employeeId),
    staleTime: 60_000,
    placeholderData: options?.placeholder,
  });
}

export function useUpdateEmployeeCache() {
  const queryClient = useQueryClient();
  const companyId = useActiveCompanyId();
  return useCallback(
    (employeeId: string, data: Employee) => {
      queryClient.setQueryData(queryKeys.employee(companyId, employeeId), data);
    },
    [queryClient, companyId],
  );
}
