import type { QueryClient } from '@tanstack/react-query';
import { getEmployee } from '@/api/employees';
import { getTeams } from '@/api/teams';
import { queryKeys } from '@/lib/queryKeys';

/** Précharge le chunk JS et les données critiques avant navigation vers une fiche. */
export function prefetchEmployeeDetail(
  queryClient: QueryClient,
  companyId: string,
  employeeId: string,
): void {
  void Promise.allSettled([
    import('@/pages/rh/EmployeeDetail'),
    queryClient.prefetchQuery({
      queryKey: queryKeys.employee(companyId, employeeId),
      queryFn: () => getEmployee(employeeId),
      staleTime: 60_000,
    }),
    queryClient.prefetchQuery({
      queryKey: ['teams-active'],
      queryFn: () => getTeams(false),
      staleTime: 5 * 60_000,
    }),
  ]);
}
