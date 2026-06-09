import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/api/apiClient";
import { getMedicalSettings, getKPIs } from "@/api/medicalFollowUp";
import { getRibAlerts } from "@/api/ribAlerts";
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
  const dashboardQuery = useQuery({
    queryKey: ["dashboard", "all", "sidebar-badges"],
    queryFn: async () => {
      const res = await apiClient.get<DashboardSidebarSlice>("/api/dashboard/all");
      return res.data;
    },
    enabled,
    staleTime: 60_000,
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
    staleTime: 60_000,
  });

  const medicalSettingsQuery = useQuery({
    queryKey: ["medical-follow-up", "settings", "sidebar-badges"],
    queryFn: getMedicalSettings,
    enabled,
    staleTime: 120_000,
  });

  const medicalKpisQuery = useQuery({
    queryKey: ["medical-follow-up", "kpis", "sidebar-badges"],
    queryFn: getKPIs,
    enabled: enabled && medicalSettingsQuery.data?.enabled === true,
    staleTime: 60_000,
  });

  const ribAlertsQuery = useQuery({
    queryKey: ["rib-alerts", "sidebar-badges"],
    queryFn: async () => {
      const res = await getRibAlerts({ is_read: false, is_resolved: false, limit: 1 });
      return typeof res.data.total === "number" ? res.data.total : (res.data.alerts?.length ?? 0);
    },
    enabled,
    staleTime: 60_000,
  });

  const annualReviewsQuery = useQuery({
    queryKey: ["annual-reviews", "priority-window", "sidebar-badges"],
    queryFn: async () => {
      const res = await getAllAnnualReviews();
      return countUpcomingPlannedAnnualReviews(res.data ?? []);
    },
    enabled,
    staleTime: 60_000,
  });

  const recruitmentSettingsQuery = useQuery({
    queryKey: ["recruitment", "settings", "sidebar-badges"],
    queryFn: getRecruitmentSettings,
    enabled,
    staleTime: 120_000,
  });

  const recruitmentCandidatesQuery = useQuery({
    queryKey: ["recruitment", "candidates", "sidebar-badges"],
    queryFn: () => getCandidates(),
    enabled: enabled && recruitmentSettingsQuery.data?.enabled === true,
    staleTime: 60_000,
  });

  const now = new Date();
  const schedulesYear = now.getFullYear();
  const schedulesMonth = now.getMonth() + 1;

  const workMedalsQuery = useQuery({
    queryKey: ["work-medal-summary", "sidebar-badges"],
    queryFn: getWorkMedalSummary,
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
    staleTime: 120_000,
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
    return buildCounts(
      dashboardQuery.data,
      residenceQuery.data,
      medicalDue,
      annualReviewsQuery.data,
      recruitmentDue,
      schedulesBadgeQuery.data,
      workMedalsDue,
    );
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
  ]);

  const totalRhPending = useMemo(() => {
    let s = 0;
    for (const v of Object.values(counts)) {
      s += v;
    }
    s += ribAlertsQuery.data ?? 0;
    return s;
  }, [counts, ribAlertsQuery.data]);

  const isLoading =
    enabled &&
    (dashboardQuery.isPending ||
      residenceQuery.isPending ||
      medicalSettingsQuery.isPending ||
      ribAlertsQuery.isPending ||
      annualReviewsQuery.isPending ||
      recruitmentSettingsQuery.isPending ||
      (recruitmentSettingsQuery.data?.enabled === true &&
        recruitmentCandidatesQuery.isPending) ||
      (medicalSettingsQuery.data?.enabled === true && medicalKpisQuery.isPending) ||
      schedulesBadgeQuery.isPending ||
      workMedalsQuery.isPending);

  const getCount = (url: string) => counts[url] ?? 0;

  return { getCount, counts, isLoading, totalRhPending };
}
