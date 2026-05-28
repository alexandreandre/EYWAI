import apiClient from "@/api/apiClient";
import type { AuditLogEntry } from "@/api/analytics";

export interface AdminGlobalStats {
  companies: { total: number; active: number; inactive: number };
  users: { total: number; by_role: Record<string, number> };
  employees: { total: number };
  platform_admins: { total: number };
  /** @deprecated */
  super_admins?: { total: number };
  top_companies: Array<{ id: string; name: string; employees_count: number }>;
  support_tickets?: {
    open: number;
    urgent: number;
    by_status: Record<string, number>;
  };
  scraping_alerts?: { unread: number };
  recent_activity?: PlatformAuditLogEntry[];
  recent_support_tickets?: AdminSupportTicketPreview[];
}

export interface PlatformAuditLogEntry extends AuditLogEntry {
  company_name?: string | null;
}

export interface AdminSupportTicketPreview {
  id: string;
  company_id: string;
  company_name?: string | null;
  module: string;
  urgency: string;
  status: string;
  description: string;
  created_at: string;
}

export interface AdminSupportBadges {
  pending: number;
  urgent: number;
}

export type GetPlatformAuditLogsParams = {
  company_id?: string;
  user_id?: string;
  action?: string;
  resource_type?: string;
  created_after?: string;
  created_before?: string;
  limit?: number;
  offset?: number;
};

export async function getAdminGlobalStats(): Promise<AdminGlobalStats> {
  const { data } = await apiClient.get<AdminGlobalStats>(
    "/api/super-admin/dashboard/stats",
  );
  return data;
}

export async function getPlatformAuditLogs(
  params?: GetPlatformAuditLogsParams,
): Promise<PlatformAuditLogEntry[]> {
  const { data } = await apiClient.get<PlatformAuditLogEntry[]>(
    "/api/super-admin/activity/logs",
    { params },
  );
  return data;
}

export async function getAdminSupportBadges(): Promise<AdminSupportBadges> {
  const { data } = await apiClient.get<AdminSupportBadges>(
    "/api/super-admin/dashboard/support-badges",
  );
  return data;
}

export async function listSuperAdmins(): Promise<{
  platform_admins: Array<Record<string, unknown>>;
  /** @deprecated */
  super_admins?: Array<Record<string, unknown>>;
  total: number;
}> {
  const { data } = await apiClient.get("/api/super-admin/super-admins");
  return data;
}
