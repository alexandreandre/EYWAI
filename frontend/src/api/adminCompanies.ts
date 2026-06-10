import apiClient from "@/api/apiClient";
import type {
  ActiveStatusFilter,
  AdminCompany,
} from "@/pages/admin/eywai/companies/types";

export interface CompanyGroupSummary {
  id: string;
  group_name: string;
}

export interface ListAdminCompaniesParams {
  search?: string;
  is_active?: boolean;
  limit?: number;
}

export async function listCompanyGroups(): Promise<CompanyGroupSummary[]> {
  const { data } = await apiClient.get<CompanyGroupSummary[]>("/api/company-groups/");
  return data ?? [];
}

export async function listAdminCompanies(
  params: ListAdminCompaniesParams = {},
): Promise<AdminCompany[]> {
  const { data } = await apiClient.get<{ companies?: AdminCompany[] }>(
    "/api/super-admin/companies",
    { params },
  );
  return data.companies ?? [];
}

export async function assignCompanyToGroup(
  groupId: string,
  companyId: string,
): Promise<void> {
  await apiClient.post(`/api/company-groups/${groupId}/companies/${companyId}`);
}

export async function reorderGroupCompanies(
  groupId: string,
  companyIds: string[],
): Promise<void> {
  await apiClient.post(`/api/company-groups/${groupId}/companies/reorder`, {
    company_ids: companyIds,
  });
}

export async function patchAdminCompanyStatus(
  companyId: string,
  isActive: boolean,
): Promise<void> {
  await apiClient.patch(`/api/super-admin/companies/${companyId}`, {
    is_active: isActive,
  });
}

export async function deleteAdminCompanyPermanent(
  companyId: string,
): Promise<{ message?: string }> {
  const { data } = await apiClient.delete<{ message?: string }>(
    `/api/super-admin/companies/${companyId}/permanent`,
  );
  return data;
}

export function activeStatusToApiParam(
  filter: ActiveStatusFilter,
): boolean | undefined {
  if (filter === "active") return true;
  if (filter === "inactive") return false;
  return undefined;
}
