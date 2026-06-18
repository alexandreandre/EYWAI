import apiClient from "./apiClient";
import type { EmployeeLite } from "./employees";

export interface BadgeuseStatusToday {
  is_eligible_for_badgeuse: boolean;
  reason?: string;
  date?: string;
  status_label?: string;
  current_open_since?: string | null;
  next_action?: "ENTREE" | "SORTIE";
  total_seconds?: number;
  employee_display_name?: string;
  badge_username?: string;
  qr_payload?: string;
  allow_self_toggle?: boolean;
  anomalies?: string[];
  sequences?: {
    start: string;
    end: string;
    duration_seconds: number;
  }[];
  events?: {
    id?: string | null;
    timestamp: string;
    event_type: "ENTREE" | "SORTIE";
    source: "EMPLOYE" | "RH" | "QR_SCAN";
  }[];
}

export interface BadgeQrResponse {
  qr_payload: string;
  employee_display_name: string;
  badge_username?: string;
  token_version?: number;
}

export interface ScanPunchResult {
  employee_id: string;
  employee_name: string;
  event_type: "ENTREE" | "SORTIE";
  timestamp: string;
  total_seconds_today: number;
  status_label: string;
}

export interface BadgeuseDashboardToday {
  date: string;
  present_count: number;
  not_badged_count: number;
  anomaly_count: number;
  eligible_count: number;
  last_scans: {
    id?: string | null;
    employee_id: string;
    employee_name: string;
    event_type: "ENTREE" | "SORTIE";
    timestamp: string;
    source: string;
  }[];
}

export interface BadgeuseSettings {
  allow_self_toggle: boolean;
  scan_mode_enabled: boolean;
}

export interface PunchCandidate {
  employee_id: string;
  display_name: string;
  username: string | null;
  badged_today: boolean;
  next_action: "ENTREE" | "SORTIE";
}

export interface DayAccountingFields {
  computed_seconds: number;
  accounted_seconds: number | null;
  effective_seconds: number;
  has_override: boolean;
  override_differs_from_computed?: boolean;
}

export interface DaySummary extends DayAccountingFields {
  date: string;
  status: string;
  total_seconds: number;
  sequences_count: number;
  has_anomalies: boolean;
  validated?: boolean;
  employee_id?: string;
  employee_name?: string;
}

export interface DayDetail extends DayAccountingFields {
  date: string;
  status: string;
  total_seconds: number;
  sequences_count: number;
  anomalies: string[];
  events: {
    id?: string | null;
    timestamp: string;
    event_type: "ENTREE" | "SORTIE";
    source: "EMPLOYE" | "RH" | "QR_SCAN";
  }[];
  validated?: boolean;
}

export const getMyBadgeuseStatusToday = async (day?: string): Promise<BadgeuseStatusToday> => {
  const params = day ? `?day=${encodeURIComponent(day)}` : "";
  const response = await apiClient.get(`/api/me/badgeuse/status-today${params}`);
  return response.data;
};

export const getMyBadgeQr = async (): Promise<BadgeQrResponse> => {
  const response = await apiClient.get("/api/me/badgeuse/qr");
  return response.data;
};

export const toggleMyBadge = async (): Promise<BadgeuseStatusToday> => {
  const response = await apiClient.post("/api/me/badgeuse/toggle");
  return response.data;
};

export const getBadgeusePunchCandidates = async (
  companyId: string,
  options?: { q?: string; onlyNotBadged?: boolean; limit?: number }
): Promise<PunchCandidate[]> => {
  const params = new URLSearchParams({ company_id: companyId });
  if (options?.q?.trim()) {
    params.set("q", options.q.trim());
  }
  if (options?.onlyNotBadged) {
    params.set("only_not_badged", "true");
  }
  if (options?.limit != null) {
    params.set("limit", String(options.limit));
  }
  const response = await apiClient.get(
    `/api/badgeuse/punch-candidates?${params.toString()}`
  );
  return response.data ?? [];
};

export const scanBadgeQr = async (
  companyId: string,
  payload: { qr_payload?: string; employee_id?: string; username?: string }
): Promise<ScanPunchResult> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.post(
    `/api/badgeuse/scan?${params.toString()}`,
    payload
  );
  return response.data;
};

export const getBadgeuseDashboardToday = async (
  companyId: string
): Promise<BadgeuseDashboardToday> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.get(`/api/badgeuse/dashboard/today?${params.toString()}`);
  return response.data;
};

export const getBadgeuseSettings = async (companyId: string): Promise<BadgeuseSettings> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.get(`/api/badgeuse/settings?${params.toString()}`);
  return response.data;
};

export const updateBadgeuseSettings = async (
  companyId: string,
  settings: Partial<BadgeuseSettings>
): Promise<BadgeuseSettings> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.patch(
    `/api/badgeuse/settings?${params.toString()}`,
    settings
  );
  return response.data;
};

export const getEmployeeBadgeQr = async (
  employeeId: string,
  companyId: string
): Promise<BadgeQrResponse> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.get(
    `/api/badgeuse/employees/${employeeId}/qr?${params.toString()}`
  );
  return response.data;
};

export const regenerateEmployeeBadge = async (
  employeeId: string,
  companyId: string
): Promise<BadgeQrResponse> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.post(
    `/api/badgeuse/employees/${employeeId}/regenerate-badge?${params.toString()}`
  );
  return response.data;
};

export const getEmployeeDaysSummary = async (
  employeeId: string,
  companyId: string,
  from: string,
  to: string
): Promise<DaySummary[]> => {
  const params = new URLSearchParams({
    company_id: companyId,
    from,
    to,
  });
  const response = await apiClient.get(
    `/api/badgeuse/employees/${employeeId}/days?${params.toString()}`
  );
  return response.data;
};

export const getEmployeeDayDetail = async (
  employeeId: string,
  companyId: string,
  day: string
): Promise<DayDetail> => {
  const params = new URLSearchParams({
    company_id: companyId,
  });
  const response = await apiClient.get(
    `/api/badgeuse/employees/${employeeId}/days/${day}?${params.toString()}`
  );
  return response.data;
};

export const getCompanyBadgeuseSummary = async (
  companyId: string,
  from: string,
  to: string,
  withAnomaliesOnly: boolean
): Promise<
  {
    employee_id: string;
    total_seconds: number;
    total_effective_seconds: number;
    days_with_anomalies: number;
    employee_name?: string;
  }[]
> => {
  const params = new URLSearchParams({
    company_id: companyId,
    from,
    to,
    with_anomalies_only: String(withAnomaliesOnly),
  });
  const [summaryRes, employeesRes] = await Promise.all([
    apiClient.get(`/api/badgeuse/summary?${params.toString()}`),
    apiClient.get<EmployeeLite[]>("/api/employees"),
  ]);

  const employees = employeesRes.data ?? [];
  const employeesById = new Map(
    employees.map((e) => [e.id, `${e.first_name} ${e.last_name}`] as const)
  );

  const summary: {
    employee_id: string;
    total_seconds: number;
    total_effective_seconds: number;
    days_with_anomalies: number;
  }[] = summaryRes.data ?? [];

  return summary.map((row) => ({
    ...row,
    employee_name: employeesById.get(row.employee_id),
  }));
};

export const exportBadgeuseCsvUrl = (
  companyId: string,
  from: string,
  to: string
): string => {
  const params = new URLSearchParams({
    company_id: companyId,
    from,
    to,
  });
  return `/api/badgeuse/export?${params.toString()}`;
};

export const validateEmployeeDay = async (
  employeeId: string,
  companyId: string,
  day: string
): Promise<DayDetail> => {
  const params = new URLSearchParams({
    company_id: companyId,
  });
  const response = await apiClient.post(
    `/api/badgeuse/employees/${employeeId}/days/${day}/validate?${params.toString()}`
  );
  return response.data;
};

export const addEmployeeDayEvent = async (
  employeeId: string,
  companyId: string,
  day: string,
  payload: { event_type: "ENTREE" | "SORTIE"; time: string }
): Promise<DayDetail> => {
  const params = new URLSearchParams({
    company_id: companyId,
  });
  const response = await apiClient.post(
    `/api/badgeuse/employees/${employeeId}/days/${day}/events?${params.toString()}`,
    payload
  );
  return response.data;
};

export const updateBadgeuseEvent = async (
  eventId: string,
  companyId: string,
  payload: { event_type?: "ENTREE" | "SORTIE"; time?: string; date?: string }
): Promise<DayDetail> => {
  const params = new URLSearchParams({
    company_id: companyId,
  });
  const response = await apiClient.patch(
    `/api/badgeuse/events/${eventId}?${params.toString()}`,
    payload
  );
  return response.data;
};

export const deleteBadgeuseEvent = async (
  eventId: string,
  companyId: string
): Promise<void> => {
  const params = new URLSearchParams({
    company_id: companyId,
  });
  await apiClient.delete(`/api/badgeuse/events/${eventId}?${params.toString()}`);
};

export const setEmployeeDayAccountedHours = async (
  employeeId: string,
  companyId: string,
  day: string,
  accountedSeconds: number
): Promise<DayDetail> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.patch(
    `/api/badgeuse/employees/${employeeId}/days/${day}/accounted-hours?${params.toString()}`,
    { accounted_seconds: accountedSeconds }
  );
  return response.data;
};

export const clearEmployeeDayAccountedHours = async (
  employeeId: string,
  companyId: string,
  day: string
): Promise<DayDetail> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.delete(
    `/api/badgeuse/employees/${employeeId}/days/${day}/accounted-hours?${params.toString()}`
  );
  return response.data;
};
