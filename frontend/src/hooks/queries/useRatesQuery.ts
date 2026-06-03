import { useQuery } from '@tanstack/react-query';
import { fetchAllRates } from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export function useRatesQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.rates(companyId),
    queryFn: fetchAllRates,
    enabled: enabled && Boolean(companyId),
    staleTime: 0,
  });
}
