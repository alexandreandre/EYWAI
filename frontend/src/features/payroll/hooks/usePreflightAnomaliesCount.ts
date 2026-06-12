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
  const anomalies = query.data?.anomalies ?? [];
  const openAnomalies = anomalies.filter((a) => a.status === 'a_traiter');
  const openBlockingAnomalies = openAnomalies.filter((a) => a.severity === 'bloquant');

  return {
    ...query,
    openAnomaliesCount: openAnomalies.length,
    openBlockingAnomaliesCount: openBlockingAnomalies.length,
    totalAnomalies: query.data?.total ?? 0,
  };
}
