export interface AdminCompany {
  id: string;
  company_name: string;
  siret?: string;
  email?: string;
  phone?: string;
  logo_url?: string | null;
  is_active: boolean;
  created_at: string;
  employees_count?: number;
  users_count?: number;
  group_id?: string | null;
  group_name?: string | null;
  group_display_order?: number | null;
}

export type AttachmentFilter = "all" | "in_group" | "orphan";

export type ActiveStatusFilter = "all" | "active" | "inactive";

export type CompanySortMode = "group_order" | "name" | "created_at" | "employees";

export const COMPANIES_LIST_LIMIT = 500;

export function sortAdminCompanies(
  companies: AdminCompany[],
  mode: CompanySortMode,
): AdminCompany[] {
  const sorted = [...companies];
  switch (mode) {
    case "group_order":
      return sorted.sort((a, b) => {
        const ao = a.group_display_order ?? Number.MAX_SAFE_INTEGER;
        const bo = b.group_display_order ?? Number.MAX_SAFE_INTEGER;
        if (ao !== bo) return ao - bo;
        return a.company_name.localeCompare(b.company_name, "fr");
      });
    case "name":
      return sorted.sort((a, b) =>
        a.company_name.localeCompare(b.company_name, "fr"),
      );
    case "created_at":
      return sorted.sort(
        (a, b) =>
          new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
      );
    case "employees":
      return sorted.sort(
        (a, b) => (b.employees_count ?? 0) - (a.employees_count ?? 0),
      );
    default:
      return sorted;
  }
}
