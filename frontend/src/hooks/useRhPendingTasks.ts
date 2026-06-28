import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { getCetPending } from '@/api/cet';
import { getRttYearEndOverview } from '@/api/leaveSettings';
import { getMedicalSettings, getKPIs } from '@/api/medicalFollowUp';
import { getRibAlerts } from '@/api/ribAlerts';
import { getPendingSignaturesRH } from '@/api/signatures';
import { listOnboardingHub } from '@/api/onboarding';
import {
  getAllAnnualReviews,
  countUpcomingPlannedAnnualReviews,
} from '@/api/annualReviews';
import {
  countRecruitmentPriorityCandidates,
  getCandidates,
  getRecruitmentSettings,
} from '@/api/recruitment';
import {
  countSchedulesToEnter,
  fetchAllEmployeesOverview,
  type SchedulesEmployeeInput,
} from '@/lib/schedulesOverview';
import { getModulationWorkflowStatus } from '@/api/modulation';
import { getWorkMedalSummary } from '@/api/workMedals';
import { isRecruitmentPriorityCandidate } from '@/api/recruitment';
import { ONBOARDING_LOOKBACK_DAYS } from '@/lib/onboardingUtils';
import { RIB_ALERTS_UI_ENABLED } from '@/lib/productFeatureFlags';
import {
  buildRhPendingTasks,
  rhPendingTasksToSidebarCounts,
  sumRhPendingActions,
  type RhPendingTaskItem,
} from '@/lib/rhPendingTasks';

interface DashboardSlice {
  actions: { pendingAbsences: number; pendingExpenses: number };
  alerts: {
    obsoleteRates: number;
    expiringContracts: number;
    endOfTrialPeriods: number;
  };
}

interface ResidenceSlice {
  total_expire: number;
  total_a_renouveler: number;
  total_a_renseigner: number;
}

const STALE = 30_000;

/**
 * File unifiée des actions RH à traiter — même périmètre que la pastille « Tableau de bord » sidebar.
 */
export function useRhPendingTasks(enabled: boolean, companyId?: string | null) {
  const dashboardQuery = useQuery({
    queryKey: ['dashboard', 'all', 'sidebar-badges'],
    queryFn: async () => {
      const res = await apiClient.get<DashboardSlice>('/api/dashboard/all');
      return res.data;
    },
    enabled,
    staleTime: STALE,
  });

  const residenceQuery = useQuery({
    queryKey: ['dashboard', 'residence-permit-stats', 'sidebar-badges'],
    queryFn: async () => {
      const res = await apiClient.get<ResidenceSlice>(
        '/api/dashboard/residence-permit-stats',
      );
      return res.data;
    },
    enabled,
    staleTime: STALE,
  });

  const medicalSettingsQuery = useQuery({
    queryKey: ['medical-follow-up', 'settings', 'sidebar-badges'],
    queryFn: getMedicalSettings,
    enabled,
    staleTime: STALE,
  });

  const medicalKpisQuery = useQuery({
    queryKey: ['medical-follow-up', 'kpis', 'sidebar-badges'],
    queryFn: getKPIs,
    enabled: enabled && medicalSettingsQuery.data?.enabled === true,
    staleTime: STALE,
  });

  const ribAlertsQuery = useQuery({
    queryKey: ['rib-alerts', 'sidebar-badges'],
    queryFn: async () => {
      const res = await getRibAlerts({ is_read: false, is_resolved: false, limit: 1 });
      return typeof res.data.total === 'number'
        ? res.data.total
        : (res.data.alerts?.length ?? 0);
    },
    enabled: enabled && RIB_ALERTS_UI_ENABLED,
    staleTime: STALE,
  });

  const annualReviewsQuery = useQuery({
    queryKey: ['annual-reviews', 'priority-window', 'sidebar-badges'],
    queryFn: async () => {
      const res = await getAllAnnualReviews();
      return countUpcomingPlannedAnnualReviews(res.data ?? []);
    },
    enabled,
    staleTime: STALE,
  });

  const recruitmentSettingsQuery = useQuery({
    queryKey: ['recruitment', 'settings', 'sidebar-badges'],
    queryFn: getRecruitmentSettings,
    enabled,
    staleTime: STALE,
  });

  const recruitmentCandidatesQuery = useQuery({
    queryKey: ['recruitment', 'candidates', 'sidebar-badges'],
    queryFn: () => getCandidates(),
    enabled: enabled && recruitmentSettingsQuery.data?.enabled === true,
    staleTime: STALE,
  });

  const now = new Date();
  const schedulesYear = now.getFullYear();
  const schedulesMonth = now.getMonth() + 1;

  const schedulesBadgeQuery = useQuery({
    queryKey: ['schedules', 'sidebar-badges', schedulesYear, schedulesMonth],
    queryFn: async () => {
      const empRes = await apiClient.get<SchedulesEmployeeInput[]>('/api/employees');
      const employees = empRes.data ?? [];
      if (employees.length === 0) return 0;
      const rows = await fetchAllEmployeesOverview(employees, schedulesYear, schedulesMonth);
      return countSchedulesToEnter(rows);
    },
    enabled,
    staleTime: STALE,
  });

  const workMedalsQuery = useQuery({
    queryKey: ['work-medal-summary', 'sidebar-badges'],
    queryFn: getWorkMedalSummary,
    enabled,
    staleTime: STALE,
  });

  const rttYearEndQuery = useQuery({
    queryKey: ['rtt-year-end', 'sidebar-badges'],
    queryFn: () => getRttYearEndOverview(),
    enabled,
    staleTime: 60_000,
  });

  const modulationWorkflowQuery = useQuery({
    queryKey: ['modulation', 'workflow-status', 'sidebar-badges'],
    queryFn: getModulationWorkflowStatus,
    enabled,
    staleTime: STALE,
  });

  const cetPendingQuery = useQuery({
    queryKey: ['cet', 'pending', 'sidebar-badges'],
    queryFn: getCetPending,
    enabled,
    staleTime: STALE,
  });

  const pendingSignaturesQuery = useQuery({
    queryKey: ['signatures', 'pending-rh', 'sidebar-badges', companyId],
    queryFn: getPendingSignaturesRH,
    enabled: enabled && Boolean(companyId),
    staleTime: STALE,
  });

  const onboardingQuery = useQuery({
    queryKey: ['onboarding', 'hub-dashboard', 'sidebar-badges', companyId],
    queryFn: () => listOnboardingHub(companyId as string, ONBOARDING_LOOKBACK_DAYS),
    enabled: enabled && Boolean(companyId),
    staleTime: STALE,
  });

  const recruitmentPreview = useMemo(() => {
    const candidates = recruitmentCandidatesQuery.data;
    if (!candidates?.length) return null;
    const pending = candidates.filter(isRecruitmentPriorityCandidate);
    if (pending.length === 0) return null;
    return pending
      .slice(0, 2)
      .map((c) => `${c.first_name} ${c.last_name}`)
      .join(' · ');
  }, [recruitmentCandidatesQuery.data]);

  const onboardingItems = onboardingQuery.data?.items ?? [];
  const incompleteEmployees = onboardingItems.filter((item) => !item.profile_complete);
  const incompleteProfiles =
    onboardingQuery.data?.kpis.profile_incomplete ?? incompleteEmployees.length;
  const onboardingPreview =
    incompleteEmployees.length > 0
      ? incompleteEmployees
          .slice(0, 2)
          .map((item) => `${item.first_name} ${item.last_name}`.trim())
          .join(' · ')
      : null;
  const onboardingHref =
    incompleteEmployees.length === 1
      ? `/employees/${incompleteEmployees[0].employee_id}`
      : '/onboarding';

  const rttClosable =
    rttYearEndQuery.data?.reminder_active
      ? rttYearEndQuery.data.employees.filter((e) => e.closure_required).length
      : 0;

  const ribTotal = ribAlertsQuery.data ?? 0;

  const items: RhPendingTaskItem[] = useMemo(() => {
    const dash = dashboardQuery.data;
    const residence = residenceQuery.data;
    const medicalEnabled = medicalSettingsQuery.data?.enabled === true;
    const medicalKpis = medicalKpisQuery.data;
    const recruitmentEnabled = recruitmentSettingsQuery.data?.enabled === true;

    return buildRhPendingTasks({
      pendingAbsences: dash?.actions.pendingAbsences ?? 0,
      pendingExpenses: dash?.actions.pendingExpenses ?? 0,
      obsoleteRates: dash?.alerts.obsoleteRates ?? 0,
      expiringContracts: dash?.alerts.expiringContracts ?? 0,
      endOfTrialPeriods: dash?.alerts.endOfTrialPeriods ?? 0,
      residenceExpire: residence?.total_expire ?? 0,
      residenceRenew: residence?.total_a_renouveler ?? 0,
      residenceMissing: residence?.total_a_renseigner ?? 0,
      medicalEnabled,
      medicalOverdue: medicalKpis?.overdue_count ?? 0,
      medicalDue30: medicalKpis?.due_within_30_count ?? 0,
      ribTotal,
      annualReviewsUpcoming: annualReviewsQuery.data ?? 0,
      recruitmentEnabled,
      recruitmentPending:
        recruitmentEnabled && recruitmentCandidatesQuery.data
          ? countRecruitmentPriorityCandidates(recruitmentCandidatesQuery.data)
          : 0,
      schedulesDue: schedulesBadgeQuery.data ?? 0,
      workMedalsAwaiting: workMedalsQuery.data?.awaiting_rh ?? 0,
      rttClosable,
      modulationAlerts: modulationWorkflowQuery.data?.alert_count ?? 0,
      cetPending: cetPendingQuery.data?.length ?? 0,
      incompleteProfiles,
      pendingSignatures: pendingSignaturesQuery.data?.total ?? 0,
      recruitmentPreview,
      onboardingPreview,
      onboardingHref,
    });
  }, [
    dashboardQuery.data,
    residenceQuery.data,
    medicalSettingsQuery.data?.enabled,
    medicalKpisQuery.data,
    ribTotal,
    annualReviewsQuery.data,
    recruitmentSettingsQuery.data?.enabled,
    recruitmentCandidatesQuery.data,
    schedulesBadgeQuery.data,
    workMedalsQuery.data?.awaiting_rh,
    rttClosable,
    modulationWorkflowQuery.data?.alert_count,
    cetPendingQuery.data,
    incompleteProfiles,
    pendingSignaturesQuery.data?.total,
    recruitmentPreview,
    onboardingPreview,
    onboardingHref,
  ]);

  const dashboardOnlyIds = new Set(['onboardingProfiles', 'pendingSignatures']);
  const totalActions = sumRhPendingActions(items);
  const sidebarTotal = sumRhPendingActions(
    items.filter((item) => !dashboardOnlyIds.has(item.id)),
  );
  const sidebarCounts = rhPendingTasksToSidebarCounts(items);

  const hasCoreData = Boolean(dashboardQuery.data && residenceQuery.data);

  /** Bloque l’UI seulement tant qu’on n’a pas les sources principales (pas les requêtes lentes type plannings). */
  const isLoading =
    enabled &&
    !hasCoreData &&
    (dashboardQuery.isPending ||
      residenceQuery.isPending ||
      medicalSettingsQuery.isPending);

  const isRefreshing =
    enabled &&
    hasCoreData &&
    (dashboardQuery.isFetching ||
      residenceQuery.isFetching ||
      schedulesBadgeQuery.isFetching ||
      cetPendingQuery.isFetching);

  const queryInFlight = (q: { isPending: boolean; isFetching: boolean }) =>
    q.isPending || q.isFetching;

  const isPayrollPipelineLoading =
    enabled &&
    (queryInFlight(dashboardQuery) || queryInFlight(schedulesBadgeQuery));

  return {
    items,
    totalActions,
    sidebarTotal,
    sidebarCounts,
    isLoading,
    isRefreshing,
    isPayrollPipelineLoading,
    getCount: (url: string) => sidebarCounts[url] ?? 0,
  };
}
