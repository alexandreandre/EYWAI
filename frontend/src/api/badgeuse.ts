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
  events?: {
    id?: string | null;
    timestamp: string;
    event_type: "ENTREE" | "SORTIE";
    source: "EMPLOYE" | "RH";
  }[];
}

export interface DaySummary {
  date: string;
  status: string;
  total_seconds: number;
  sequences_count: number;
  has_anomalies: boolean;
  validated?: boolean;
  employee_id?: string;
  employee_name?: string;
}

export interface DayDetail {
  date: string;
  status: string;
  total_seconds: number;
  sequences_count: number;
  anomalies: string[];
  events: {
    id?: string | null;
    timestamp: string;
    event_type: "ENTREE" | "SORTIE";
    source: "EMPLOYE" | "RH";
  }[];
  validated?: boolean;
}

export const getMyBadgeuseStatusToday = async (day?: string): Promise<BadgeuseStatusToday> => {
  const params = day ? `?day=${encodeURIComponent(day)}` : "";
  const response = await apiClient.get(`/api/me/badgeuse/status-today${params}`);
  return response.data;
};

export const toggleMyBadge = async (): Promise<BadgeuseStatusToday> => {
  const response = await apiClient.post("/api/me/badgeuse/toggle");
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


