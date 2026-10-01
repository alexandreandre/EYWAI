import { useQuery } from '@tanstack/react-query';
import { getEmployeeExits } from '@/api/employeeExits';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

/** Tous les départs de la société active (une requête). */
export function useEmployeeExitsQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.employeeExits(companyId),
    queryFn: () => getEmployeeExits(),
    enabled: enabled && Boolean(companyId),
    retry: false,
    staleTime: 30_000,
  });
}
