import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import apiClient from "@/api/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";

export type CurrentEmployeeRow = {
  id: string;
  first_name: string;
  last_name: string;
  email?: string | null;
};

/**
 * Résout l’employé courant (fiche salarié) à partir de l’email du compte connecté
 * et de l’entreprise active (GET /api/employees).
 */
export function useCurrentEmployee() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();

  const query = useQuery({
    queryKey: ["current-employee", activeCompany?.company_id, user?.email],
    queryFn: async () => {
      const res = await apiClient.get<CurrentEmployeeRow[]>("/api/employees");
      return res.data ?? [];
    },
    enabled: Boolean(user?.email && activeCompany?.company_id),
  });

  const employee = useMemo((): CurrentEmployeeRow | null => {
    if (!user?.email || !query.data?.length) return null;
    const em = user.email.toLowerCase();
    return query.data.find((e) => (e.email || "").toLowerCase() === em) ?? null;
  }, [query.data, user?.email]);

  const notConfigured =
    !query.isLoading && !query.isError && Boolean(activeCompany?.company_id) && !employee;

  return {
    employee,
    isLoading: query.isLoading,
    isError: query.isError,
    error: query.error,
    refetch: query.refetch,
    notConfigured,
  };
}
