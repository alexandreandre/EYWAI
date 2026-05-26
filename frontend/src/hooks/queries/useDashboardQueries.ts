import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import {
  ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS,
  countUpcomingPlannedAnnualReviews,
  getAllAnnualReviews,
} from '@/api/annualReviews';
import { getKPIs, getMedicalSettings } from '@/api/medicalFollowUp';
import {
  countRecruitmentPriorityCandidates,
  getCandidates,
  getRecruitmentSettings,
} from '@/api/recruitment';
import * as ribAlertsApi from '@/api/ribAlerts';
import { getPendingSignaturesRH } from '@/api/signatures';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export function useDashboardAllQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.dashboardAll(companyId),
    queryFn: async () => {
      const res = await apiClient.get('/api/dashboard/all');
      return res.data;
    },
    enabled: enabled && Boolean(companyId),
  });
}

export function useResidencePermitStatsQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.residencePermitStats(companyId),
    queryFn: async () => {
      const res = await apiClient.get('/api/dashboard/residence-permit-stats');
      return res.data as {
        total_expire: number;
        total_a_renouveler: number;
        total_a_renseigner: number;
        total_valide: number;
      };
    },
    enabled: enabled && Boolean(companyId),
    placeholderData: {
      total_expire: 0,
      total_a_renouveler: 0,
      total_a_renseigner: 0,
      total_valide: 0,
    },
  });
}

export function useRibAlertsDashboardQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.ribAlerts(companyId),
    queryFn: async () => {
      const res = await ribAlertsApi.getRibAlerts({
        is_read: false,
        is_resolved: false,
        limit: 5,
      });
      return {
        alerts: res.data.alerts ?? [],
        total:
          typeof res.data.total === 'number'
            ? res.data.total
            : (res.data.alerts ?? []).length,
      };
    },
    enabled: enabled && Boolean(companyId),
    placeholderData: { alerts: [], total: 0 },
  });
}

export function useMedicalDashboardQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  const settingsQuery = useQuery({
    queryKey: queryKeys.medicalSettings(companyId),
    queryFn: getMedicalSettings,
    enabled: enabled && Boolean(companyId),
  });

  const kpisQuery = useQuery({
    queryKey: queryKeys.medicalKpis(companyId),
    queryFn: getKPIs,
    enabled: enabled && Boolean(companyId) && settingsQuery.data?.enabled === true,
  });

  return {
    settingsQuery,
    kpisQuery,
    medicalModuleEnabled: settingsQuery.data?.enabled ?? false,
    medicalKpis: settingsQuery.data?.enabled ? kpisQuery.data ?? null : null,
    isLoading: settingsQuery.isLoading || (settingsQuery.data?.enabled && kpisQuery.isLoading),
    isFetching: settingsQuery.isFetching || kpisQuery.isFetching,
  };
}

export function useAnnualReviewsPriorityQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.annualReviews(companyId),
    queryFn: async () => {
      const res = await getAllAnnualReviews();
      return res.data ?? [];
    },
    enabled: enabled && Boolean(companyId),
    select: (reviews) =>
      countUpcomingPlannedAnnualReviews(reviews, ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS),
  });
}

export function useRecruitmentPriorityQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  const settingsQuery = useQuery({
    queryKey: queryKeys.recruitmentSettings(companyId),
    queryFn: getRecruitmentSettings,
    enabled: enabled && Boolean(companyId),
  });

  const candidatesQuery = useQuery({
    queryKey: queryKeys.recruitmentCandidates(companyId),
    queryFn: () => getCandidates(),
    enabled: enabled && Boolean(companyId) && settingsQuery.data?.enabled === true,
  });

  const pendingCount =
    settingsQuery.data?.enabled && candidatesQuery.data
      ? countRecruitmentPriorityCandidates(candidatesQuery.data)
      : 0;

  return {
    settingsQuery,
    candidatesQuery,
    pendingCount,
    isLoading:
      settingsQuery.isLoading ||
      (settingsQuery.data?.enabled && candidatesQuery.isLoading),
  };
}

export function usePendingSignaturesRhQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.pendingSignaturesRh(companyId),
    queryFn: getPendingSignaturesRH,
    enabled: enabled && Boolean(companyId),
  });
}
