import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getCompanySetupStatus } from '@/api/adminImport';

export function companySetupStatusQueryKey(companyId: string) {
  return ['company-setup-status', companyId] as const;
}

type Options = {
  enabled?: boolean;
  refetchInterval?: number | false;
};

/** Statut onboarding filiale — garde les données visibles pendant les refetch. */
export function useCompanySetupStatus(companyId: string, options: Options = {}) {
  const enabled = Boolean(companyId) && (options.enabled ?? true);
  return useQuery({
    queryKey: companySetupStatusQueryKey(companyId),
    queryFn: () => getCompanySetupStatus(companyId),
    enabled,
    staleTime: 30_000,
    placeholderData: (previous) => previous,
    refetchInterval: options.refetchInterval,
  });
}

export function useRefreshCompanySetupStatus() {
  const queryClient = useQueryClient();
  return (companyId: string) => {
    if (!companyId) return;
    void queryClient.invalidateQueries({ queryKey: companySetupStatusQueryKey(companyId) });
  };
}
