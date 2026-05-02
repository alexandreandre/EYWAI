/**
 * Périmètre « équipe » pour les vues manager : équipes dont l’utilisateur est
 * manager (si droits RH), sinon uniquement les salariés visibles via les
 * demandes de formation en attente de validation manager.
 */

import { useQuery } from "@tanstack/react-query";

import apiClient from "@/api/apiClient";
import { getPendingManagerApproval } from "@/api/training";
import { getTeams } from "@/api/teams";
import type { CompanyAccess } from "@/contexts/CompanyContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useCurrentEmployee } from "@/hooks/useCurrentEmployee";

export function useCanQueryRhApis(activeCompany: CompanyAccess | null): boolean {
  const r = activeCompany?.role;
  return r === "admin" || r === "rh" || r === "collaborateur_rh";
}

export function useManagerTeamMemberIds() {
  const { activeCompany } = useCompany();
  const { employee: me } = useCurrentEmployee();
  const canRh = useCanQueryRhApis(activeCompany);
  const cid = activeCompany?.company_id ?? "";

  return useQuery({
    queryKey: ["manager-team-member-ids", cid, me?.id, canRh],
    queryFn: async () => {
      const ids = new Set<string>();
      if (!cid || !me?.id) return ids;

      if (canRh) {
        const { teams } = await getTeams(false);
        const managed = teams.filter(
          (t) => t.status === "active" && t.manager_employee_id === me.id,
        );
        for (const t of managed) {
          const { data } = await apiClient.get<{ members: { id: string }[] }>(
            `/api/teams/${t.id}`,
          );
          for (const m of data?.members ?? []) ids.add(m.id);
        }
        return ids;
      }

      const pending = await getPendingManagerApproval(cid);
      for (const row of pending) ids.add(row.employee_id);
      return ids;
    },
    enabled: Boolean(cid && me?.id),
  });
}
