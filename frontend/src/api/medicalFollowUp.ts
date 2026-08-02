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
  amenagement_poste?: boolean;
}

export interface KPIs {
  overdue_count: number;
  due_within_30_count: number;
  active_total: number;
  completed_this_month: number;
}

export interface OccupationalHealthContact {
  nom?: string | null;
  adresse_rue?: string | null;
  adresse_code_postal?: string | null;
  adresse_ville?: string | null;
  telephone?: string | null;
  email?: string | null;
}

export interface MedicalSettings {
  enabled: boolean;
  occupational_health_contact?: OccupationalHealthContact | null;
}

export async function getMedicalSettings(): Promise<MedicalSettings> {
  const res = await apiClient.get<MedicalSettings>("/api/medical-follow-up/settings");
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
  body: { completed_date: string; justification?: string; amenagement_poste?: boolean }
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

export interface SendMedicalRemindersResult {
  sent: number;
  errors: number;
  message: string;
}

/** POST — envoie les notifications de rappel (entreprise active, accès RH). */
export async function sendMedicalReminders(): Promise<SendMedicalRemindersResult> {
  const res = await apiClient.post<SendMedicalRemindersResult>(
    "/api/medical-follow-up/send-reminders"
  );
  return res.data;
}

/** Obligations en retard (GET, RH). */
export async function getOverdueObligations(): Promise<ObligationListItem[]> {
  const res = await apiClient.get<ObligationListItem[]>(
    "/api/medical-follow-up/obligations/overdue"
  );
  return res.data ?? [];
}

/** Obligations à échéance dans les ``days`` prochains jours (GET, RH). */
export async function getUpcomingObligations(days: number = 30): Promise<ObligationListItem[]> {
  const res = await apiClient.get<ObligationListItem[]>(
    "/api/medical-follow-up/obligations/upcoming",
    { params: { days } }
  );
  return res.data ?? [];
}

export interface VisitTypeCompliance {
  visit_type: string;
  label: string;
  total: number;
  compliant: number;
  overdue: number;
  compliance_rate: number;
}

export interface EmployeeOverdue {
  employee_id: string;
  employee_name: string;
  obligations_overdue: number;
  most_urgent_due_date: string;
  visit_types: string[];
}

export interface ComplianceReport {
  generated_at: string;
  total_employees: number;
  total_obligations: number;
  compliant: number;
  overdue: number;
  upcoming_30: number;
  upcoming_7: number;
  compliance_rate: number;
  by_visit_type: VisitTypeCompliance[];
  employees_overdue: EmployeeOverdue[];
}

/** Rapport de conformité (GET, RH, entreprise active). */
export async function getComplianceReport(): Promise<ComplianceReport> {
  const res = await apiClient.get<ComplianceReport>(
    "/api/medical-follow-up/compliance-report"
  );
  return res.data;
}
