import { useCallback, useEffect } from "react";
import { keepPreviousData, useIsFetching } from "@tanstack/react-query";
import type { Query, QueryClient } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";
import { getAccountingConfig } from "@/api/accountingIntegration";
import {
  getAccountingMappings,
  getDispatchHistory,
  getDispatchSchedules,
  getDispatchStatus,
  getExportHistory,
  getScheduledExports,
} from "@/api/exports";

/** Intervalle de rafraîchissement des données exports tant que la page est visible. */
export const EXPORTS_REFETCH_INTERVAL_MS = 15_000;

export const EXPORTS_QUERY_KEY_PREFIXES = [
  "dispatch-status",
  "dispatch-history",
  "dispatch-schedules",
  "scheduled-exports",
  "export-history",
] as const;

/** Préfixe réservé au wizard dispatch (ne pas invalider globalement : pas de queryFn hors modal). */
export const DISPATCH_PREVIEW_QUERY_KEY = "dispatch-preview" as const;

/** Clés react-query rechargées à l'ouverture de la page Exports (onglets + cartes). */
export const EXPORTS_PAGE_QUERY_KEY_PREFIXES = [
  ...EXPORTS_QUERY_KEY_PREFIXES,
  "accounting-mappings",
  "accounting-integration-config",
] as const;

function matchesQueryPrefix(queryKey: unknown, prefixes: readonly string[]): boolean {
  if (!Array.isArray(queryKey) || typeof queryKey[0] !== "string") {
    return false;
  }
  return prefixes.includes(queryKey[0]);
}

export function isExportsPageQuery(query: Query): boolean {
  return matchesQueryPrefix(query.queryKey, EXPORTS_PAGE_QUERY_KEY_PREFIXES);
}

function exportsCurrentMonth(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

/** Options react-query : données exports toujours fraîches, refetch en arrière-plan sans vider l'UI. */
export const exportsLiveQueryOptions = {
  staleTime: 0,
  refetchOnWindowFocus: true,
  refetchOnReconnect: true,
  refetchOnMount: true,
  placeholderData: keepPreviousData,
  refetchInterval: () => {
    if (typeof document !== "undefined" && document.hidden) {
      return false;
    }
    return EXPORTS_REFETCH_INTERVAL_MS;
  },
} as const;

/** Wizard dispatch : pas de refetch global, pas de données périmées affichées pendant le fetch. */
export const exportsWizardPreviewQueryOptions = {
  staleTime: 0,
  refetchOnWindowFocus: false,
  refetchOnReconnect: false,
  refetchOnMount: true,
} as const;

function invalidateQueryPrefix(queryClient: QueryClient, prefix: string) {
  void queryClient.invalidateQueries({
    queryKey: [prefix],
    refetchType: "all",
  });
}

export function invalidateExportsQueries(queryClient: QueryClient) {
  for (const prefix of EXPORTS_QUERY_KEY_PREFIXES) {
    invalidateQueryPrefix(queryClient, prefix);
  }
}

/** Rafraîchit toutes les données affichées sur la page Exports (y compris onglets non montés). */
export function invalidateExportsPageQueries(queryClient: QueryClient) {
  invalidateExportsQueries(queryClient);
  invalidateQueryPrefix(queryClient, "accounting-mappings");
  invalidateQueryPrefix(queryClient, "accounting-integration-config");
}

/**
 * Précharge en arrière-plan les requêtes de tous les onglets Exports
 * (données prêtes avant changement d'onglet).
 */
export function prefetchExportsPageQueries(queryClient: QueryClient, companyId: string) {
  const period = exportsCurrentMonth();

  const tasks = [
    queryClient.prefetchQuery({
      queryKey: ["dispatch-status", companyId, period],
      queryFn: () => getDispatchStatus(companyId, period),
      ...exportsLiveQueryOptions,
    }),
    queryClient.prefetchQuery({
      queryKey: ["dispatch-history", companyId],
      queryFn: () => getDispatchHistory(companyId, undefined, 10),
      ...exportsLiveQueryOptions,
    }),
    queryClient.prefetchQuery({
      queryKey: ["dispatch-schedules", companyId],
      queryFn: () => getDispatchSchedules(companyId),
      ...exportsLiveQueryOptions,
    }),
    queryClient.prefetchQuery({
      queryKey: ["scheduled-exports", companyId],
      queryFn: () => getScheduledExports(companyId),
      ...exportsLiveQueryOptions,
    }),
    queryClient.prefetchQuery({
      queryKey: ["export-history", "all"],
      queryFn: () => getExportHistory(),
      ...exportsLiveQueryOptions,
    }),
    queryClient.prefetchQuery({
      queryKey: ["accounting-mappings", companyId],
      queryFn: () => getAccountingMappings(companyId),
      ...exportsLiveQueryOptions,
    }),
    queryClient.prefetchQuery({
      queryKey: ["accounting-integration-config", companyId],
      queryFn: () => getAccountingConfig(companyId),
      ...exportsLiveQueryOptions,
    }),
  ];

  void Promise.allSettled(tasks);
}

/** Invalidation + préchargement silencieux (navigation, mise à jour métier, changement d'onglet). */
export function refreshExportsPageQueries(
  queryClient: QueryClient,
  companyId?: string | null,
) {
  invalidateExportsPageQueries(queryClient);
  if (companyId) {
    prefetchExportsPageQueries(queryClient, companyId);
  }
}

/**
 * Activité de chargement des requêtes de la page Exports (premier fetch ou refetch).
 */
export function useExportsPageQueriesActivity() {
  const isFetching =
    useIsFetching({
      predicate: isExportsPageQuery,
    }) > 0;

  const isInitialLoading =
    useIsFetching({
      predicate: (query) => isExportsPageQuery(query) && query.state.status === "pending",
    }) > 0;

  const isRefreshing = isFetching && !isInitialLoading;

  return { isFetching, isInitialLoading, isRefreshing };
}

/**
 * Rafraîchit les exports à l'ouverture de la page, au changement d'entreprise
 * et au retour sur l'onglet navigateur (refetch en arrière-plan).
 */
export function useExportsPageAutoRefresh(
  queryClient: QueryClient,
  companyId: string | null | undefined,
) {
  const location = useLocation();

  const refresh = useCallback(() => {
    refreshExportsPageQueries(queryClient, companyId);
  }, [queryClient, companyId]);

  useEffect(() => {
    if (!companyId || location.pathname !== "/exports") return;
    refresh();
  }, [companyId, location.pathname, refresh]);

  useEffect(() => {
    if (!companyId) return;
    const onVisibility = () => {
      if (!document.hidden && location.pathname === "/exports") refresh();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [companyId, location.pathname, refresh]);
}
