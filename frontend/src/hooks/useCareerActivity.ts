import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { getDocuments } from "@/api/documents";
import { getPromotions } from "@/api/promotions";
import type { PromotionStatus, PromotionType } from "@/api/promotions";
import type { CareerActivityFilters } from "@/components/career/types";
import {
  applyClientFilters,
  AVENANTS_QUERY_KEY,
  buildCareerActivityItems,
  countItemsByTab,
  filterItemsByTab,
} from "@/lib/careerActivity";

export function useCareerActivity(
  companyId: string,
  filters: CareerActivityFilters,
) {
  const promotionsQuery = useQuery({
    queryKey: [
      "promotions",
      filters.year === "all" ? null : filters.year,
      filters.status === "all" ? null : filters.status,
      filters.type === "all" ? null : filters.type,
      filters.search || null,
      companyId,
    ],
    queryFn: async () => {
      const res = await getPromotions({
        year: filters.year === "all" ? undefined : filters.year,
        status:
          filters.status === "all" ? undefined : (filters.status as PromotionStatus),
        promotion_type:
          filters.type === "all" ? undefined : (filters.type as PromotionType),
        search: filters.search || undefined,
      });
      return res.data;
    },
    enabled: Boolean(companyId),
  });

  const avenantsQuery = useQuery({
    queryKey: [...AVENANTS_QUERY_KEY, companyId],
    queryFn: () => getDocuments({ document_type: "avenant_salaire" }),
    enabled: Boolean(companyId),
  });

  const promotions = promotionsQuery.data ?? [];
  const avenants = avenantsQuery.data ?? [];

  const allItems = useMemo(
    () => buildCareerActivityItems(promotions, avenants),
    [promotions, avenants],
  );

  const items = useMemo(() => {
    const byTab = filterItemsByTab(allItems, filters.tab);
    return applyClientFilters(byTab, filters);
  }, [allItems, filters]);

  const tabCounts = useMemo(
    () =>
      countItemsByTab(allItems, {
        search: filters.search,
        year: filters.year,
        status: filters.status,
        type: filters.type,
      }),
    [allItems, filters.search, filters.year, filters.status, filters.type],
  );

  return {
    items,
    tabCounts,
    promotions,
    avenants,
    isLoading: promotionsQuery.isLoading || avenantsQuery.isLoading,
    isError: promotionsQuery.isError || avenantsQuery.isError,
    error: promotionsQuery.error ?? avenantsQuery.error,
    refetch: () => {
      void promotionsQuery.refetch();
      void avenantsQuery.refetch();
    },
  };
}
