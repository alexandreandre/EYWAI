import apiClient from "./apiClient";

export type ProfessionalInterviewStatus = "up_to_date" | "due_soon" | "overdue" | "unknown";
export type SixYearReviewStatus = "validated" | "in_progress" | "not_validated" | "unknown";

export type LegalObligationStatus = {
  employee_id: string;
  employee_name: string;
  hire_date?: string | null;
  last_professional_interview_date?: string | null;
  professional_interview_status: ProfessionalInterviewStatus;
  professional_interview_next_due?: string | null;
  six_year_review_status: SixYearReviewStatus;
  six_year_criteria_met: boolean;
  six_year_next_due?: string | null;
  last_six_year_review_date?: string | null;
  criteria_training_completed: boolean;
  criteria_certification_obtained: boolean;
  criteria_career_evolution: boolean;
};

export type LegalObligationOverride = {
  employee_id: string;
  criteria_training_completed: boolean;
  criteria_certification_obtained: boolean;
  criteria_career_evolution: boolean;
  notes?: string | null;
};

export type LegalObligationOverrideWrite = Omit<LegalObligationOverride, "employee_id">;

export async function getAllStatus(
  statusFilter?: ProfessionalInterviewStatus,
): Promise<LegalObligationStatus[]> {
  const q = statusFilter
    ? `?status_filter=${encodeURIComponent(statusFilter)}`
    : "";
  const res = await apiClient.get<LegalObligationStatus[]>(`/api/legal-obligations${q}`);
  return res.data ?? [];
}

export async function getEmployeeStatus(employeeId: string): Promise<LegalObligationStatus> {
  const res = await apiClient.get<LegalObligationStatus>(`/api/legal-obligations/${employeeId}`);
  return res.data;
}

export async function saveOverride(
  employeeId: string,
  data: LegalObligationOverrideWrite,
): Promise<LegalObligationOverride> {
  const res = await apiClient.put<LegalObligationOverride>(
    `/api/legal-obligations/${employeeId}/override`,
    data,
  );
  return res.data;
}

export async function getOverdueCount(): Promise<{ count: number }> {
  const res = await apiClient.get<{ count: number }>("/api/legal-obligations/count/overdue");
  return res.data;
}
