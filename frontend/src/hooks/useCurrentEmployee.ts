import { useQuery } from "@tanstack/react-query";
import axios from "axios";

import apiClient from "@/api/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";

export type CurrentEmployeeRow = {
  id: string;
  first_name: string;
  last_name: string;
  email?: string | null;
  is_subject_to_residence_permit?: boolean | null;
  residence_permit_type?: string | null;
  residence_permit_number?: string | null;
  residence_permit_expiry_date?: string | null;
};

/**
 * Fiche salarié liée au compte connecté (GET /api/employees/me).
 */
export function useCurrentEmployee() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();

  const query = useQuery({
    queryKey: ["current-employee", activeCompany?.company_id, user?.id],
    queryFn: async (): Promise<CurrentEmployeeRow | null> => {
      try {
        const res = await apiClient.get<CurrentEmployeeRow>("/api/employees/me");
        return res.data;
      } catch (err) {
        if (axios.isAxiosError(err) && err.response?.status === 404) {
          return null;
        }
        throw err;
      }
    },
    enabled: Boolean(user?.id && activeCompany?.company_id),
  });

  const employee = query.data ?? null;

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
