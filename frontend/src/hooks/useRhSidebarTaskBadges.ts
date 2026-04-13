import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import apiClient from "@/api/apiClient";
import { getMedicalSettings, getKPIs } from "@/api/medicalFollowUp";

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

  const counts = useMemo(() => {
    const medicalDue =
      medicalSettingsQuery.data?.enabled && medicalKpisQuery.data
        ? medicalKpisQuery.data.overdue_count + medicalKpisQuery.data.due_within_30_count
        : undefined;
    return buildCounts(dashboardQuery.data, residenceQuery.data, medicalDue);
  }, [
    dashboardQuery.data,
    residenceQuery.data,
    medicalSettingsQuery.data?.enabled,
    medicalKpisQuery.data,
  ]);

  const isLoading =
    enabled &&
    (dashboardQuery.isPending ||
      residenceQuery.isPending ||
      medicalSettingsQuery.isPending ||
      (medicalSettingsQuery.data?.enabled === true && medicalKpisQuery.isPending));

  const getCount = (url: string) => counts[url] ?? 0;

  return { getCount, counts, isLoading };
}
