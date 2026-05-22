/**
 * API client — parcours d'onboarding (checklist post-embauche).
 */

import apiClient from "./apiClient";

export interface OnboardingTask {
  id: string;
  checklist_id: string;
  title: string;
  description?: string | null;
  category: string;
  is_completed: boolean;
  completed_at?: string | null;
  due_days?: number | null;
  position: number;
}

export interface OnboardingChecklist {
  id: string;
  employee_id: string;
  company_id: string;
  created_at: string;
  completed_at?: string | null;
  tasks: OnboardingTask[];
  nb_total: number;
  nb_completed: number;
  progress_pct: number;
}

export interface OnboardingHubItem {
  employee_id: string;
  first_name: string;
  last_name: string;
  job_title?: string | null;
  hire_date?: string | null;
  days_since_hire?: number | null;
  checklist_id?: string | null;
  has_checklist: boolean;
  progress_pct: number;
  nb_total: number;
  nb_completed: number;
  nb_overdue: number;
  completed_at?: string | null;
  checklist_created_at?: string | null;
}

export interface OnboardingHubKpis {
  in_progress: number;
  overdue_tasks: number;
  completed_this_month: number;
}

export interface OnboardingHubList {
  items: OnboardingHubItem[];
  kpis: OnboardingHubKpis;
  lookback_days: number;
}

export async function listOnboardingHub(
  companyId: string,
  lookbackDays = 90,
): Promise<OnboardingHubList> {
  const res = await apiClient.get<OnboardingHubList>("/api/onboarding", {
    headers: { "X-Active-Company": companyId },
    params: { lookback_days: lookbackDays },
  });
  return res.data;
}

export async function getOnboarding(
  employeeId: string,
  companyId: string
): Promise<OnboardingChecklist> {
  const res = await apiClient.get<OnboardingChecklist>(`/api/onboarding/${employeeId}`, {
    headers: { "X-Active-Company": companyId },
  });
  return res.data;
}

export async function getMyOnboarding(companyId: string): Promise<OnboardingChecklist> {
  const res = await apiClient.get<OnboardingChecklist>("/api/onboarding/me", {
    headers: { "X-Active-Company": companyId },
  });
  return res.data;
}

export async function completeTask(
  employeeId: string,
  taskId: string,
  companyId: string
): Promise<{ success: boolean }> {
  const res = await apiClient.post<{ success: boolean }>(
    `/api/onboarding/${employeeId}/tasks/${taskId}/complete`,
    {},
    { headers: { "X-Active-Company": companyId } }
  );
  return res.data;
}

export async function uncompleteTask(
  employeeId: string,
  taskId: string,
  companyId: string
): Promise<{ success: boolean }> {
  const res = await apiClient.post<{ success: boolean }>(
    `/api/onboarding/${employeeId}/tasks/${taskId}/uncomplete`,
    {},
    { headers: { "X-Active-Company": companyId } }
  );
  return res.data;
}
