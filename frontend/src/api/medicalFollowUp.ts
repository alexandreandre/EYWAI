/**
 * API client for the Medical Follow-up module (obligations VIP, SIR, reprise, etc.)
 */

import apiClient from "./apiClient";

export interface ObligationListItem {
  id: string;
  company_id: string;
  employee_id: string;
  visit_type: string;
  trigger_type: string;
  due_date: string;
  priority: number;
  status: string;
  justification?: string | null;
  planned_date?: string | null;
  completed_date?: string | null;
  rule_source: string;
  collective_agreement_idcc?: string | null;
  request_motif?: string | null;
  request_date?: string | null;
  employee_first_name?: string | null;
  employee_last_name?: string | null;
}

export interface KPIs {
  overdue_count: number;
  due_within_30_count: number;
  active_total: number;
  completed_this_month: number;
}

export async function getMedicalSettings(): Promise<{ enabled: boolean }> {
  const res = await apiClient.get<{ enabled: boolean }>("/api/medical-follow-up/settings");
  return res.data;
}

export async function getObligations(params?: {
  employee_id?: string;
  visit_type?: string;
  status?: string;
  priority?: number;
  due_from?: string;
  due_to?: string;
}): Promise<ObligationListItem[]> {
  const searchParams = new URLSearchParams();
  if (params?.employee_id) searchParams.set("employee_id", params.employee_id);
  if (params?.visit_type) searchParams.set("visit_type", params.visit_type);
  if (params?.status) searchParams.set("status", params.status);
  if (params?.priority != null) searchParams.set("priority", String(params.priority));
  if (params?.due_from) searchParams.set("due_from", params.due_from);
  if (params?.due_to) searchParams.set("due_to", params.due_to);
  const q = searchParams.toString();
  const url = q ? `/api/medical-follow-up/obligations?${q}` : "/api/medical-follow-up/obligations";
  const res = await apiClient.get<ObligationListItem[]>(url);
  return res.data ?? [];
}

export async function getKPIs(): Promise<KPIs> {
  const res = await apiClient.get<KPIs>("/api/medical-follow-up/kpis");
  return res.data;
}

export async function markPlanified(
  obligationId: string,
  body: { planned_date: string; justification?: string }
): Promise<void> {
  await apiClient.patch(`/api/medical-follow-up/obligations/${obligationId}/planified`, body);
}

export async function markCompleted(
  obligationId: string,
  body: { completed_date: string; justification?: string }
): Promise<void> {
  await apiClient.patch(`/api/medical-follow-up/obligations/${obligationId}/completed`, body);
}

export async function createOnDemand(body: {
  employee_id: string;
  request_motif: string;
  request_date: string;
}): Promise<void> {
  await apiClient.post("/api/medical-follow-up/obligations/on-demand", body);
}

export async function getObligationsForEmployee(employeeId: string): Promise<ObligationListItem[]> {
  const res = await apiClient.get<ObligationListItem[]>(
    `/api/medical-follow-up/obligations/employee/${employeeId}`
  );
  return res.data ?? [];
}

export async function getMyObligations(): Promise<ObligationListItem[]> {
  const res = await apiClient.get<ObligationListItem[]>("/api/medical-follow-up/me");
  return res.data ?? [];
}
