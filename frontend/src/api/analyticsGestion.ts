import apiClient from "@/api/apiClient";

export interface AnalyticsGestionPeriod {
  period_start: string;
  period_end: string;
  year: number;
  calendar_year: number;
  calendar_month: number;
}

export interface EntretiensAnalytics {
  actionable_count: number;
  overdue_count: number;
  upcoming_14d_count: number;
  closure_rate_pct: number;
  by_status: Record<string, number>;
}

export interface ConformiteAnalytics {
  certifications_expired: number;
  certifications_expiring: number;
  legal_obligations_overdue: number;
  legal_obligations_due_soon: number;
  legal_obligations_up_to_date: number;
}

export interface FormationAnalytics {
  budget_consumption_pct: number;
  budget_alert_level: "none" | "warning" | "critical";
  budget_consumed: number;
  budget_envelope: number;
  training_consumed_year: number;
  evaluations_count: number;
  evaluations_average: number | null;
}

export interface CalendriersAnalytics {
  total: number;
  saisis: number;
  a_saisir: number;
  avec_ecart: number;
  conflits_absences: number;
  progress_percent: number;
}

export interface MedicalEmployeeOverdue {
  employee_id: string;
  employee_name: string;
  obligations_overdue: number;
  most_urgent_due_date: string;
}

export interface MedicalAnalytics {
  overdue_count: number;
  due_within_30_count: number;
  active_total: number;
  completed_this_month: number;
  compliance_rate_pct: number;
  employees_overdue_top: MedicalEmployeeOverdue[];
}

export interface ObjectivesAnalytics {
  achievement_rate_pct: number | null;
}

export interface CarriereAnalytics {
  total_promotions: number;
  approval_rate_pct: number;
  average_salary_increase_pct: number | null;
  promotions_by_month: Record<string, number>;
  promotions_draft_count: number;
  avenants_pending_signature: number;
}

export interface CseMeetingPreview {
  id: string;
  title: string;
  meeting_date: string;
  meeting_time: string | null;
}

export interface CseAnalytics {
  mandate_alerts_count: number;
  election_alerts_count: number;
  election_critical_count: number;
  delegation_over_quota_count: number;
  delegation_consumed_hours: number;
  delegation_quota_hours: number;
  upcoming_meetings: CseMeetingPreview[];
}

export interface AnalyticsGestionResponse {
  period: AnalyticsGestionPeriod;
  entretiens: EntretiensAnalytics;
  conformite: ConformiteAnalytics;
  formation: FormationAnalytics;
  calendriers: CalendriersAnalytics;
  medical: MedicalAnalytics;
  objectives: ObjectivesAnalytics;
  carriere: CarriereAnalytics;
  cse: CseAnalytics;
}

export type GetAnalyticsGestionParams = {
  period_start: string;
  period_end: string;
};

export async function getAnalyticsGestion(
  companyId: string | null | undefined,
  params: GetAnalyticsGestionParams,
): Promise<AnalyticsGestionResponse> {
  const headers =
    companyId && companyId.length > 0
      ? { "X-Active-Company": companyId }
      : undefined;
  const { data } = await apiClient.get<AnalyticsGestionResponse>(
    "/api/dashboard/analytics-gestion",
    {
      headers,
      params,
    },
  );
  return data;
}
