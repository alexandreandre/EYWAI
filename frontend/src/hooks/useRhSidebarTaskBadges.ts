import { useEffect, useMemo, useRef } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { getCetPending } from "@/api/cet";
import { invalidateRhSidebarBadges } from "@/lib/invalidateRhSidebarBadges";
import apiClient from "@/api/apiClient";
import { getRttYearEndOverview } from '@/api/leaveSettings';
import { getMedicalSettings, getKPIs } from "@/api/medicalFollowUp";
import { getRibAlerts } from "@/api/ribAlerts";
import { RIB_ALERTS_UI_ENABLED } from "@/lib/productFeatureFlags";
import {
  getAllAnnualReviews,
  countUpcomingPlannedAnnualReviews,
} from "@/api/annualReviews";
import {
  countRecruitmentPriorityCandidates,
  getCandidates,
  getRecruitmentSettings,
} from "@/api/recruitment";
import {
  countSchedulesToEnter,
  fetchAllEmployeesOverview,
  type SchedulesEmployeeInput,
} from "@/lib/schedulesOverview";
import { getModulationWorkflowStatus } from '@/api/modulation';
import { getWorkMedalSummary } from "@/api/workMedals";

/** Données utiles à la sidebar (sous-ensemble de GET /api/dashboard/all). */
interface DashboardSidebarSlice {
  actions: {
    pendingAbsences: number;
    pendingExpenses: number;
  };
  alerts: {
    obsoleteRates: number;
    expiringContracts: number;
    endOfTrialPeriods: number;
  };
}

interface ResidencePermitStatsSlice {
  total_expire: number;
  total_a_renouveler: number;
  total_a_renseigner: number;
}

function buildCounts(
  dashboard: DashboardSidebarSlice | undefined,
  residence: ResidencePermitStatsSlice | undefined,
  medicalDue: number | undefined,
  annualReviewsDue: number | undefined,
  recruitmentDue: number | undefined,
  schedulesDue: number | undefined,
  workMedalsDue: number | undefined,
): Record<string, number> {
  const out: Record<string, number> = {};

  if (dashboard) {
    out["/leaves"] = dashboard.actions.pendingAbsences;
    out["/expenses"] = dashboard.actions.pendingExpenses;
    out["/rates"] = dashboard.alerts.obsoleteRates;
    out["/employees"] =
      dashboard.alerts.expiringContracts + dashboard.alerts.endOfTrialPeriods;
  }

  if (residence) {
    out["/residence-permits"] =
      residence.total_expire +
      residence.total_a_renouveler +
      residence.total_a_renseigner;
  }

  if (medicalDue != null && medicalDue > 0) {
    out["/medical-follow-up"] = medicalDue;
  }

  if (annualReviewsDue != null && annualReviewsDue > 0) {
    out["/annual-reviews"] = annualReviewsDue;
  }

  if (recruitmentDue != null && recruitmentDue > 0) {
    out["/recruitment"] = recruitmentDue;
  }

  if (schedulesDue != null && schedulesDue > 0) {
    out["/schedules"] = schedulesDue;
  }

  if (workMedalsDue != null && workMedalsDue > 0) {
    out["/company"] = workMedalsDue;
  }

  return out;
}

/**
 * Compteurs « à traiter » pour la navigation RH (sidebar).
 * Pastilles agrégées côté UI : présence si count > 0 ; affichage du nombre sur les sous-liens.
 */
export function useRhSidebarTaskBadges(enabled: boolean) {
  const queryClient = useQueryClient();
  const location = useLocation();

  const prevPathRef = useRef<string | null>(null);
  useEffect(() => {
    if (!enabled) return;
    const prev = prevPathRef.current;
    prevPathRef.current = location.pathname;
    if (prev === null || prev === location.pathname) return;
    void invalidateRhSidebarBadges(queryClient);
  }, [enabled, location.pathname, queryClient]);

  const dashboardQuery = useQuery({
    queryKey: ["dashboard", "all", "sidebar-badges"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardSidebarSlice>("/api/dashboard/all");
      return res.data;
    },
    enabled,
    staleTime: 30_000,
  });

  const residenceQuery = useQuery({
    queryKey: ["dashboard", "residence-permit-stats", "sidebar-badges"],
    queryFn: async () => {
      const res = await apiClient.get<ResidencePermitStatsSlice>(
        "/api/dashboard/residence-permit-stats",
      );
      return res.data;
    },
    enabled,
    staleTime: 30_000,
  });

  const medicalSettingsQuery = useQuery({
    queryKey: ["medical-follow-up", "settings", "sidebar-badges"],
    queryFn: getMedicalSettings,
    enabled,
    staleTime: 30_000,
  });

  const medicalKpisQuery = useQuery({
    queryKey: ["medical-follow-up", "kpis", "sidebar-badges"],
    queryFn: getKPIs,
    enabled: enabled && medicalSettingsQuery.data?.enabled === true,
    staleTime: 30_000,
  });

  const ribAlertsQuery = useQuery({
    queryKey: ["rib-alerts", "sidebar-badges"],
    queryFn: async () => {
      const res = await getRibAlerts({ is_read: false, is_resolved: false, limit: 1 });
      return typeof res.data.total === "number" ? res.data.total : (res.data.alerts?.length ?? 0);
    },
    enabled: enabled && RIB_ALERTS_UI_ENABLED,
    staleTime: 30_000,
  });

  const annualReviewsQuery = useQuery({
    queryKey: ["annual-reviews", "priority-window", "sidebar-badges"],
    queryFn: async () => {
      const res = await getAllAnnualReviews();
      return countUpcomingPlannedAnnualReviews(res.data ?? []);
    },
    enabled,
    staleTime: 30_000,
  });

  const recruitmentSettingsQuery = useQuery({
    queryKey: ["recruitment", "settings", "sidebar-badges"],
    queryFn: getRecruitmentSettings,
    enabled,
    staleTime: 30_000,
  });

  const recruitmentCandidatesQuery = useQuery({
    queryKey: ["recruitment", "candidates", "sidebar-badges"],
    queryFn: () => getCandidates(),
    enabled: enabled && recruitmentSettingsQuery.data?.enabled === true,
    staleTime: 30_000,
  });

  const now = new Date();
  const schedulesYear = now.getFullYear();
  const schedulesMonth = now.getMonth() + 1;

  const workMedalsQuery = useQuery({
    queryKey: ["work-medal-summary", "sidebar-badges"],
    queryFn: getWorkMedalSummary,
    enabled,
    staleTime: 30_000,
  });

  const rttYearEndQuery = useQuery({
    queryKey: ["rtt-year-end", "sidebar-badges"],
    queryFn: () => getRttYearEndOverview(),
    enabled,
    staleTime: 60_000,
  });

  const schedulesBadgeQuery = useQuery({
    queryKey: ["schedules", "sidebar-badges", schedulesYear, schedulesMonth],
    queryFn: async () => {
      const empRes = await apiClient.get<SchedulesEmployeeInput[]>("/api/employees");
      const employees = empRes.data ?? [];
      if (employees.length === 0) return 0;
      const rows = await fetchAllEmployeesOverview(employees, schedulesYear, schedulesMonth);
      return countSchedulesToEnter(rows);
    },
    enabled,
    staleTime: 30_000,
  });

  const modulationWorkflowQuery = useQuery({
    queryKey: ["modulation", "workflow-status", "sidebar-badges"],
    queryFn: getModulationWorkflowStatus,
    enabled,
    staleTime: 30_000,
  });

  const cetPendingQuery = useQuery({
    queryKey: ["cet", "pending", "sidebar-badges"],
    queryFn: getCetPending,
    enabled,
    staleTime: 30_000,
  });

  const counts = useMemo(() => {
    const medicalDue =
      medicalSettingsQuery.data?.enabled && medicalKpisQuery.data
        ? medicalKpisQuery.data.overdue_count + medicalKpisQuery.data.due_within_30_count
        : undefined;
    const recruitmentDue =
      recruitmentSettingsQuery.data?.enabled && recruitmentCandidatesQuery.data
        ? countRecruitmentPriorityCandidates(recruitmentCandidatesQuery.data)
        : undefined;
    const workMedalsDue = workMedalsQuery.data?.awaiting_rh ?? undefined;
    const base = buildCounts(
      dashboardQuery.data,
      residenceQuery.data,
      medicalDue,
      annualReviewsQuery.data,
      recruitmentDue,
      schedulesBadgeQuery.data,
      workMedalsDue,
    );
    if (rttYearEndQuery.data?.reminder_active) {
      const closable = rttYearEndQuery.data.employees.filter(
        (e) => e.closure_required,
      ).length;
      if (closable > 0) {
        base["/leaves"] = (base["/leaves"] ?? 0) + closable;
      }
    }
    const modAlerts = modulationWorkflowQuery.data?.alert_count ?? 0;
    if (modAlerts > 0) {
      base["/suivi-temps-travail"] = modAlerts;
    }
    const cetPending = cetPendingQuery.data?.length ?? 0;
    if (cetPending > 0) {
      base["/suivi-cet"] = cetPending;
    }
    return base;
  }, [
    dashboardQuery.data,
    residenceQuery.data,
    medicalSettingsQuery.data?.enabled,
    medicalKpisQuery.data,
    annualReviewsQuery.data,
    recruitmentSettingsQuery.data?.enabled,
    recruitmentCandidatesQuery.data,
    schedulesBadgeQuery.data,
    workMedalsQuery.data?.awaiting_rh,
    rttYearEndQuery.data,
    modulationWorkflowQuery.data?.alert_count,
    cetPendingQuery.data,
  ]);

  const totalRhPending = useMemo(() => {
    let s = 0;
    for (const v of Object.values(counts)) {
      s += v;
    }
    s += RIB_ALERTS_UI_ENABLED ? (ribAlertsQuery.data ?? 0) : 0;
    return s;
  }, [counts, ribAlertsQuery.data]);

  const queryInFlight = (q: { isPending: boolean; isFetching: boolean }) =>
    q.isPending || q.isFetching;

  const isLoading =
    enabled &&
    (queryInFlight(dashboardQuery) ||
      queryInFlight(residenceQuery) ||
      queryInFlight(medicalSettingsQuery) ||
      queryInFlight(ribAlertsQuery) ||
      queryInFlight(annualReviewsQuery) ||
      queryInFlight(recruitmentSettingsQuery) ||
      (recruitmentSettingsQuery.data?.enabled === true &&
        queryInFlight(recruitmentCandidatesQuery)) ||
      (medicalSettingsQuery.data?.enabled === true && queryInFlight(medicalKpisQuery)) ||
      queryInFlight(schedulesBadgeQuery) ||
      queryInFlight(workMedalsQuery) ||
      queryInFlight(modulationWorkflowQuery));

  /** Parcours paie (calendriers, congés, frais) : gris tant que ces compteurs ne sont pas stabilisés. */
  const isPayrollPipelineLoading =
    enabled &&
    (queryInFlight(dashboardQuery) || queryInFlight(schedulesBadgeQuery));

  const getCount = (url: string) => counts[url] ?? 0;

  return { getCount, counts, isLoading, isPayrollPipelineLoading, totalRhPending };
}
