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
