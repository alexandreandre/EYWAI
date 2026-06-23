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

export interface DeleteAllCompanyEmployeesResult {
  success: boolean;
  company_id: string;
  company_name: string;
  requested_count: number;
  removed_count: number;
  removed: Array<{ employee_id: string; employee_name: string }>;
  failed: Array<{ employee_id: string; employee_name: string; error: string }>;
}

export async function deleteAllCompanyEmployees(
  companyId: string,
): Promise<DeleteAllCompanyEmployeesResult> {
  const { data } = await apiClient.delete<DeleteAllCompanyEmployeesResult>(
    `/api/super-admin/companies/${companyId}/employees`,
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

export interface AdminCompanyStats {
  employees_count: number;
  users_count: number;
  users_by_role: Record<string, number>;
}

export interface AdminCompanyDetails {
  id: string;
  company_name: string;
  raison_sociale?: string | null;
  siret?: string | null;
  siren?: string | null;
  code_naf?: string | null;
  naf_ape?: string | null;
  legal_form?: string | null;
  email?: string | null;
  phone?: string | null;
  website?: string | null;
  urssaf_number?: string | null;
  adresse_rue?: string | null;
  adresse_code_postal?: string | null;
  adresse_ville?: string | null;
  nom_signataire_rh?: string | null;
  qualite_signataire_rh?: string | null;
  address?: Record<string, string> | null;
  logo_url?: string | null;
  logo_scale?: number;
  is_active: boolean;
  created_at: string;
  stats: AdminCompanyStats;
  jei_enabled?: boolean;
  date_creation_etablissement?: string | null;
  taux_exoneration?: number | null;
}

export type AdminCompanyUpdate = Partial<
  Pick<
    AdminCompanyDetails,
    | "company_name"
    | "raison_sociale"
    | "siret"
    | "siren"
    | "code_naf"
    | "naf_ape"
    | "legal_form"
    | "email"
    | "phone"
    | "website"
    | "urssaf_number"
    | "adresse_rue"
    | "adresse_code_postal"
    | "adresse_ville"
    | "nom_signataire_rh"
    | "qualite_signataire_rh"
    | "is_active"
    | "jei_enabled"
    | "date_creation_etablissement"
    | "taux_exoneration"
  >
>;

export async function fetchAdminCompanyDetails(
  companyId: string,
): Promise<AdminCompanyDetails> {
  const { data } = await apiClient.get<AdminCompanyDetails>(
    `/api/super-admin/companies/${companyId}`,
  );
  return data;
}

export async function patchAdminCompany(
  companyId: string,
  body: AdminCompanyUpdate,
): Promise<AdminCompanyDetails> {
  const { data } = await apiClient.patch<{ company: AdminCompanyDetails }>(
    `/api/super-admin/companies/${companyId}`,
    body,
  );
  return data.company;
}
