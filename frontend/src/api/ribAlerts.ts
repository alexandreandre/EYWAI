// src/api/ribAlerts.ts
// API pour les alertes RIB (modification et doublon)

import apiClient from "./apiClient";

export type RibAlertType = "rib_modified" | "rib_duplicate";
export type RibAlertSeverity = "info" | "warning" | "error";

export interface RibAlert {
  id: string;
  company_id: string;
  employee_id: string | null;
  alert_type: RibAlertType;
  severity: RibAlertSeverity;
  title: string;
  message: string;
  details?: {
    old_iban_masked?: string;
    new_iban_masked?: string;
    iban_masked?: string;
    duplicate_employees?: Array<{ id: string; first_name: string; last_name: string }>;
  };
  is_read: boolean;
  is_resolved: boolean;
  resolved_at: string | null;
  resolution_note: string | null;
  created_at: string;
}

export interface RibAlertsListParams {
  is_read?: boolean;
  is_resolved?: boolean;
  alert_type?: RibAlertType;
  employee_id?: string;
  limit?: number;
  offset?: number;
}

export interface RibAlertsListResponse {
  alerts: RibAlert[];
  total: number;
}

export const getRibAlerts = (params?: RibAlertsListParams) => {
  const searchParams = new URLSearchParams();
  if (params?.is_read !== undefined) searchParams.set("is_read", String(params.is_read));
  if (params?.is_resolved !== undefined) searchParams.set("is_resolved", String(params.is_resolved));
  if (params?.alert_type) searchParams.set("alert_type", params.alert_type);
  if (params?.employee_id) searchParams.set("employee_id", params.employee_id);
  if (params?.limit !== undefined) searchParams.set("limit", String(params.limit));
  if (params?.offset !== undefined) searchParams.set("offset", String(params.offset));
  const qs = searchParams.toString();
  return apiClient.get<RibAlertsListResponse>(`/api/rib-alerts${qs ? `?${qs}` : ""}`);
};

export const markRibAlertRead = (alertId: string) => {
  return apiClient.patch<{ success: boolean }>(`/api/rib-alerts/${alertId}/read`);
};

export const markRibAlertResolved = (alertId: string, resolutionNote?: string) => {
  return apiClient.patch<{ success: boolean }>(`/api/rib-alerts/${alertId}/resolve`, {
    resolution_note: resolutionNote ?? null,
  });
};
