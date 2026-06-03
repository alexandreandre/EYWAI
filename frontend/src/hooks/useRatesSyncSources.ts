import { useQuery } from '@tanstack/react-query';

import { fetchRatesSyncSources } from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';
import { manifestHasRunningSources } from '@/lib/ratesSyncManifest';
import { readPersistedSyncIds } from '@/lib/ratesSyncStorage';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

export function useRatesSyncSources() {
  const companyId = useActiveCompanyId();
  const hasPersistedSync = readPersistedSyncIds().length > 0;
  return useQuery({
    queryKey: [...queryKeys.rates(companyId), 'sync-sources'],
    queryFn: fetchRatesSyncSources,
    enabled: Boolean(companyId),
    staleTime: hasPersistedSync ? 0 : 5_000,
    refetchOnMount: hasPersistedSync ? 'always' : true,
    refetchOnWindowFocus: true,
    refetchInterval: (query) =>
      manifestHasRunningSources(query.state.data) || readPersistedSyncIds().length > 0
        ? 2_000
        : false,
  });
}
