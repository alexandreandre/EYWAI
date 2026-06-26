import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getCompanySetupStatus, type CompanySetupStatus } from '@/api/adminImport';
import { invalidateDsnCoverageForCompany } from '@/lib/dsnCoverageCache';

export function companySetupStatusQueryKey(companyId: string) {
  return ['company-setup-status', companyId] as const;
}

type Options = {
  enabled?: boolean;
  refetchInterval?: number | false;
};

/** Ne renvoie le statut que s'il correspond à la filiale demandée. */
export function scopedCompanySetupStatus(
  status: CompanySetupStatus | undefined,
  companyId: string,
): CompanySetupStatus | undefined {
  if (!companyId || !status) return undefined;
  return status.company_id === companyId ? status : undefined;
}

/** Statut onboarding filiale — garde les données visibles pendant les refetch (même filiale). */
export function useCompanySetupStatus(companyId: string, options: Options = {}) {
  const enabled = Boolean(companyId) && (options.enabled ?? true);
  const query = useQuery({
    queryKey: companySetupStatusQueryKey(companyId),
    queryFn: () => getCompanySetupStatus(companyId),
    enabled,
    staleTime: 30_000,
    placeholderData: (previousData, previousQuery) => {
      if (previousQuery?.queryKey[1] === companyId) {
        return previousData;
      }
      return undefined;
    },
    refetchInterval: options.refetchInterval,
  });

  const data = scopedCompanySetupStatus(query.data, companyId);

  return {
    ...query,
    data,
    isLoading: enabled && query.isLoading && !data,
  };
}

export function useRefreshCompanySetupStatus() {
  const queryClient = useQueryClient();
  return (companyId: string) => {
    if (!companyId) return;
    invalidateDsnCoverageForCompany(queryClient, companyId);
  };
}
