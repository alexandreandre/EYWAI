import type { QueryClient } from '@tanstack/react-query';

import type { RatesResponse, RatesSyncJob } from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';
import type { Cotisation } from '@/lib/ratesUtils';

function normalizeId(value: string): string {
  return value.trim().toLowerCase();
}

export function patchRatesLastCheckedInCache(
  queryClient: QueryClient,
  companyId: string | undefined,
  patch: {
    rateKeys?: string[];
    cotisationIds?: string[];
    checkedAt: string;
  },
): void {
  const queryKey = queryKeys.rates(companyId);
  const current = queryClient.getQueryData<RatesResponse>(queryKey);
  if (!current) return;

  const next: RatesResponse = { ...current };
  const checkedAt = patch.checkedAt;

  for (const rateKey of patch.rateKeys ?? []) {
    const category = next[rateKey];
    if (!category) continue;
    next[rateKey] = { ...category, last_checked_at: checkedAt };
  }

  const cotisationIds = (patch.cotisationIds ?? []).map(normalizeId);
  if (cotisationIds.length > 0 && next.cotisations) {
    const configData = next.cotisations.config_data as { cotisations?: Cotisation[] };
    const items = configData.cotisations;
    if (Array.isArray(items)) {
      const cotisationIdsSet = new Set(cotisationIds);
      const updatedItems = items.map((item) =>
        cotisationIdsSet.has(normalizeId(item.id))
          ? { ...item, last_checked_at: checkedAt }
          : item,
      );
      next.cotisations = {
        ...next.cotisations,
        config_data: {
          ...configData,
          cotisations: updatedItems,
        },
      };
    }
  }

  queryClient.setQueryData(queryKey, next);
}

export function applyCompletedSyncJobsToRatesCache(
  queryClient: QueryClient,
  companyId: string | undefined,
  jobs: RatesSyncJob[],
): void {
  for (const job of jobs) {
    if (job.status !== 'completed' || job.success === false) continue;
    const checkedAt = job.completed_at ?? new Date().toISOString();
    patchRatesLastCheckedInCache(queryClient, companyId, {
      rateKeys: job.rate_keys,
      cotisationIds: job.cotisation_ids,
      checkedAt,
    });
  }
}
