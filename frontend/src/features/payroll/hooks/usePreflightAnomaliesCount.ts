import { useQuery } from '@tanstack/react-query';
import { getPreflightAnomalies } from '@/api/payrollPreflight';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';

export function usePreflightAnomalies(year: number, month: number, enabled = true) {
  const companyId = useActiveCompanyId();

  return useQuery({
    queryKey: queryKeys.payrollPreflight(companyId, year, month),
    queryFn: () => getPreflightAnomalies(year, month),
    enabled: enabled && year > 0 && month >= 1 && month <= 12,
    staleTime: 30_000,
  });
}

export function usePreflightAnomaliesCount(year: number, month: number, enabled = true) {
  const query = usePreflightAnomalies(year, month, enabled);
  return {
    ...query,
    openAnomaliesCount: query.data?.total_open ?? 0,
    totalAnomalies: query.data?.total ?? 0,
  };
}
