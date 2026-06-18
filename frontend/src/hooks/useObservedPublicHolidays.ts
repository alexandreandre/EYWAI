import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getCompanySettings } from '@/api/company';
import { useCompany } from '@/contexts/CompanyContext';
import {
  getDefaultObservedHolidayIds,
  normalizeObservedHolidayIds,
  type FrenchPublicHolidayId,
} from '@/lib/frenchPublicHolidays';
import { queryKeys } from '@/lib/queryKeys';

function parseObservedHolidayIds(settings: Record<string, unknown> | undefined): FrenchPublicHolidayId[] {
  const publicHolidays = settings?.public_holidays;
  if (!publicHolidays || typeof publicHolidays !== 'object') {
    return getDefaultObservedHolidayIds();
  }
  const rawIds = (publicHolidays as { observed_holiday_ids?: unknown }).observed_holiday_ids;
  if (!Array.isArray(rawIds)) {
    return getDefaultObservedHolidayIds();
  }
  return normalizeObservedHolidayIds(
    rawIds.filter((id): id is FrenchPublicHolidayId => typeof id === 'string')
  );
}

export function useObservedPublicHolidays() {
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? '';

  const query = useQuery({
    queryKey: queryKeys.companySettings(activeCompanyId),
    queryFn: getCompanySettings,
    enabled: Boolean(activeCompanyId),
    staleTime: 60_000,
  });

  const observedHolidayIds = useMemo(
    () => parseObservedHolidayIds(query.data?.settings),
    [query.data?.settings]
  );

  return {
    observedHolidayIds,
    isLoading: query.isLoading,
    settings: query.data,
  };
}
