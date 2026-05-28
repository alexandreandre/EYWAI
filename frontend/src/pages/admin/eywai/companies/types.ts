export interface AdminCompany {
  id: string;
  company_name: string;
  siret?: string;
  email?: string;
  phone?: string;
  is_active: boolean;
  created_at: string;
  employees_count?: number;
  users_count?: number;
  group_id?: string | null;
  group_name?: string | null;
}

export type AttachmentFilter = "all" | "in_group" | "orphan";

export type ActiveStatusFilter = "all" | "active" | "inactive";

export const COMPANIES_LIST_LIMIT = 500;
