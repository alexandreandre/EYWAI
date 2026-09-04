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
import { filterPresentEmployees } from '@/lib/employmentStatus';
import { getModulationWorkflowStatus } from '@/api/modulation';
import { getWorkMedalSummary } from '@/api/workMedals';
import { isRecruitmentPriorityCandidate } from '@/api/recruitment';
import { ONBOARDING_LOOKBACK_DAYS } from '@/lib/onboardingUtils';
import { RIB_ALERTS_UI_ENABLED } from '@/lib/productFeatureFlags';
import { moisDePaieParDefaut } from '@/features/payroll/utils/payrollMonth';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { useAuth } from '@/contexts/AuthContext';
import { isPayrollFocusActive } from '@/lib/payrollFocus';
import { filterTasksToPayrollFocus } from '@/lib/rhPendingTasks';
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
export function useRhPendingTasks(enabled: boolean, companyIdOverride?: string | null) {
  const { user } = useAuth();
  const payrollFocus = isPayrollFocusActive(user);
  const activeCompanyId = useActiveCompanyId();
  const companyId = companyIdOverride ?? activeCompanyId ?? null;
  const companyEnabled = enabled && Boolean(companyId);

  const dashboardQuery = useQuery({
    queryKey: ['dashboard', 'all', 'sidebar-badges', companyId],
    queryFn: async () => {
      const res = await apiClient.get<DashboardSlice>('/api/dashboard/all');
      return res.data;
    },
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const residenceQuery = useQuery({
    queryKey: ['dashboard', 'residence-permit-stats', 'sidebar-badges', companyId],
    queryFn: async () => {
      const res = await apiClient.get<ResidenceSlice>(
        '/api/dashboard/residence-permit-stats',
      );
      return res.data;
    },
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const medicalSettingsQuery = useQuery({
    queryKey: ['medical-follow-up', 'settings', 'sidebar-badges', companyId],
    queryFn: getMedicalSettings,
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const medicalKpisQuery = useQuery({
    queryKey: ['medical-follow-up', 'kpis', 'sidebar-badges', companyId],
    queryFn: getKPIs,
    enabled: companyEnabled && medicalSettingsQuery.data?.enabled === true,
    staleTime: STALE,
  });

  const ribAlertsQuery = useQuery({
    queryKey: ['rib-alerts', 'sidebar-badges', companyId],
    queryFn: async () => {
      const res = await getRibAlerts({ is_read: false, is_resolved: false, limit: 1 });
      return typeof res.data.total === 'number'
        ? res.data.total
        : (res.data.alerts?.length ?? 0);
    },
    enabled: companyEnabled && RIB_ALERTS_UI_ENABLED,
    staleTime: STALE,
  });

  const annualReviewsQuery = useQuery({
    queryKey: ['annual-reviews', 'priority-window', 'sidebar-badges', companyId],
    queryFn: async () => {
      const res = await getAllAnnualReviews();
      return countUpcomingPlannedAnnualReviews(res.data ?? []);
    },
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const recruitmentSettingsQuery = useQuery({
    queryKey: ['recruitment', 'settings', 'sidebar-badges', companyId],
    queryFn: getRecruitmentSettings,
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const recruitmentCandidatesQuery = useQuery({
    queryKey: ['recruitment', 'candidates', 'sidebar-badges', companyId],
    queryFn: () => getCandidates(),
    enabled: companyEnabled && recruitmentSettingsQuery.data?.enabled === true,
    staleTime: STALE,
  });

  // Mois de PAIE en préparation (jusqu'au 15 : le mois précédent) — le badge
  // « Plannings du mois » et le verrou « Lancer la paie » regardent le même
  // mois : début septembre, on prépare la paie d'août, pas les calendriers
  // vierges de septembre (retour Gaëlle 03/09).
  const { year: schedulesYear, month: schedulesMonth } = moisDePaieParDefaut(
    new Date()
  );

  const schedulesBadgeQuery = useQuery({
    queryKey: ['schedules', 'sidebar-badges', companyId, schedulesYear, schedulesMonth],
    queryFn: async () => {
      const empRes = await apiClient.get<SchedulesEmployeeInput[]>('/api/employees');
      const employees = filterPresentEmployees(empRes.data ?? []);
      if (employees.length === 0) return 0;
      const rows = await fetchAllEmployeesOverview(employees, schedulesYear, schedulesMonth);
      return countSchedulesToEnter(rows);
    },
    enabled: companyEnabled,
    // Ce badge coûte 3 requêtes PAR salarié (calendrier prévu, heures réelles,
    // absences) : ~260 appels sur une société de 86. Avec le staleTime commun
    // (30 s), la sidebar relançait la rafale à chaque navigation — avec des
    // échecs CORS intermittents sous charge. Une pastille « calendriers à
    // saisir » peut être fraîche à 5 minutes près ; les mutations passent par
    // invalidateRhSidebarBadges pour forcer le refresh immédiat.
    staleTime: 5 * 60_000,
  });

  const workMedalsQuery = useQuery({
    queryKey: ['work-medal-summary', 'sidebar-badges', companyId],
    queryFn: getWorkMedalSummary,
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const rttYearEndQuery = useQuery({
    queryKey: ['rtt-year-end', 'sidebar-badges', companyId],
    queryFn: () => getRttYearEndOverview(),
    enabled: companyEnabled,
    staleTime: 60_000,
  });

  const modulationWorkflowQuery = useQuery({
    queryKey: ['modulation', 'workflow-status', 'sidebar-badges', companyId],
    queryFn: getModulationWorkflowStatus,
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const cetPendingQuery = useQuery({
    queryKey: ['cet', 'pending', 'sidebar-badges', companyId],
    queryFn: getCetPending,
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const pendingSignaturesQuery = useQuery({
    queryKey: ['signatures', 'pending-rh', 'sidebar-badges', companyId],
    queryFn: getPendingSignaturesRH,
    enabled: companyEnabled,
    staleTime: STALE,
  });

  const onboardingQuery = useQuery({
    queryKey: ['onboarding', 'hub-dashboard', 'sidebar-badges', companyId],
    queryFn: () => listOnboardingHub(companyId as string, ONBOARDING_LOOKBACK_DAYS),
    enabled: companyEnabled,
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

    const built = buildRhPendingTasks({
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

    return payrollFocus ? filterTasksToPayrollFocus(built) : built;
  }, [
    payrollFocus,
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
    companyEnabled &&
    !hasCoreData &&
    (dashboardQuery.isPending ||
      residenceQuery.isPending ||
      medicalSettingsQuery.isPending);

  const isRefreshing =
    companyEnabled &&
    hasCoreData &&
    (dashboardQuery.isFetching ||
      residenceQuery.isFetching ||
      schedulesBadgeQuery.isFetching ||
      cetPendingQuery.isFetching);

  const queryInFlight = (q: { isPending: boolean; isFetching: boolean }) =>
    q.isPending || q.isFetching;

  const isPayrollPipelineLoading =
    companyEnabled &&
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
