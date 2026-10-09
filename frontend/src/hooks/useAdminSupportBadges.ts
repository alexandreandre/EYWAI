import { useQuery } from "@tanstack/react-query";
import { getAdminSupportBadges } from "@/api/adminMartine";

export function useAdminSupportBadges() {
  return useQuery({
    queryKey: ["admin", "support-badges"],
    queryFn: getAdminSupportBadges,
    refetchInterval: 60_000,
    staleTime: 30_000,
  });
}
