import { useQuery } from '@tanstack/react-query';

import { fetchRatesSyncSources } from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

export function useRatesSyncSources() {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: [...queryKeys.rates(companyId), 'sync-sources'],
    queryFn: fetchRatesSyncSources,
    enabled: Boolean(companyId),
    staleTime: 60_000,
  });
}
