import apiClient from "./apiClient";

export type ObjectiveStatus =
  | "draft"
  | "active"
  | "achieved"
  | "partially_achieved"
  | "not_achieved"
  | "cancelled";

export type ObjectiveType = "quantitative" | "qualitative";

export type ObjectiveMilestone = {
  id: string;
  objective_id: string;
  milestone_date: string;
  expected_value: number;
  actual_value?: number | null;
  comment?: string | null;
  updated_by?: string | null;
  updated_at?: string | null;
};

export type ObjectiveCheckin = {
  id: string;
  objective_id: string;
  checkin_date: string;
  progress_note: string;
  updated_by?: string | null;
  updated_at?: string | null;
};

export type EmployeeObjective = {
  id: string;
  company_id: string;
  employee_id?: string | null;
  service_id?: string | null;
  parent_objective_id?: string | null;
  title: string;
  type: ObjectiveType | string;
  period_year: number;
  status: ObjectiveStatus | string;
  description?: string | null;
  kpi_label?: string | null;
  kpi_unit?: string | null;
  kpi_target_value?: number | null;
  kpi_initial_value?: number | null;
  due_date?: string | null;
  weight?: number | null;
  annual_review_id?: string | null;
  notes?: string | null;
  evaluation_date?: string | null;
  final_achievement_rate?: number | null;
  evaluation_comment?: string | null;
  evaluated_in_review_id?: string | null;
  last_modified_by?: string | null;
  created_by?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  milestones: ObjectiveMilestone[];
  checkins: ObjectiveCheckin[];
  employee_name?: string | null;
  service_name?: string | null;
};

export type CompanyService = {
  id: string;
  company_id: string;
  name: string;
  created_at?: string | null;
};

export type MilestoneCreate = {
  milestone_date: string;
  expected_value: number;
  comment?: string | null;
};

export type MilestoneUpdate = {
  expected_value?: number;
  actual_value?: number | null;
  comment?: string | null;
};

export type CheckinCreate = {
  checkin_date: string;
  progress_note: string;
};

export type ObjectiveCreate = {
  employee_id?: string | null;
  service_id?: string | null;
  title: string;
  type: ObjectiveType;
  period_year: number;
  status?: ObjectiveStatus;
  description?: string | null;
  kpi_label?: string | null;
  kpi_unit?: string | null;
  kpi_target_value?: number | null;
  kpi_initial_value?: number | null;
  due_date?: string | null;
  weight?: number | null;
  annual_review_id?: string | null;
  notes?: string | null;
  milestones?: MilestoneCreate[];
};

export type ObjectiveUpdate = Partial<ObjectiveCreate>;

export type ObjectiveEvaluate = {
  final_achievement_rate: number;
  status: ObjectiveStatus;
  evaluation_comment?: string | null;
  evaluation_date?: string | null;
  evaluated_in_review_id?: string | null;
};

export type DeclineToTeamResult = { created_count: number };

export type AchievementRateResponse = { rate: number | null };

export async function getObjectives(params?: {
  employee_id?: string;
  service_id?: string;
  period_year?: number;
  status?: string;
  include_inactive?: boolean;
}): Promise<EmployeeObjective[]> {
  const sp = new URLSearchParams();
  if (params?.employee_id) sp.set("employee_id", params.employee_id);
  if (params?.service_id) sp.set("service_id", params.service_id);
  if (params?.period_year != null) sp.set("period_year", String(params.period_year));
  if (params?.status) sp.set("status", params.status);
  if (params?.include_inactive) sp.set("include_inactive", "true");
  const q = sp.toString();
  const res = await apiClient.get<EmployeeObjective[]>(`/api/objectives${q ? `?${q}` : ""}`);
  return res.data ?? [];
}

export async function getObjective(id: string): Promise<EmployeeObjective> {
  const res = await apiClient.get<EmployeeObjective>(`/api/objectives/${id}`);
  return res.data;
}

export async function createObjective(body: ObjectiveCreate): Promise<EmployeeObjective> {
  const res = await apiClient.post<EmployeeObjective>("/api/objectives", body);
  return res.data;
}

export async function updateObjective(
  id: string,
  body: ObjectiveUpdate,
): Promise<EmployeeObjective> {
  const res = await apiClient.put<EmployeeObjective>(`/api/objectives/${id}`, body);
  return res.data;
}

export async function cancelObjective(id: string): Promise<void> {
  await apiClient.post(`/api/objectives/${id}/cancel`);
}

export async function deleteObjective(id: string): Promise<void> {
  await apiClient.delete(`/api/objectives/${id}`);
}

export async function evaluateObjective(
  id: string,
  body: ObjectiveEvaluate,
): Promise<EmployeeObjective> {
  const res = await apiClient.post<EmployeeObjective>(`/api/objectives/${id}/evaluate`, body);
  return res.data;
}

export async function declineObjectiveToTeam(id: string): Promise<DeclineToTeamResult> {
  const res = await apiClient.post<DeclineToTeamResult>(`/api/objectives/${id}/decline-to-team`);
  return res.data;
}

export async function getPreviousYearObjectives(id: string): Promise<EmployeeObjective[]> {
  const res = await apiClient.get<EmployeeObjective[]>(`/api/objectives/${id}/previous-year`);
  return res.data ?? [];
}

export async function getAchievementRate(periodYear: number): Promise<AchievementRateResponse> {
  const res = await apiClient.get<AchievementRateResponse>(
    `/api/objectives/achievement-rate?period_year=${periodYear}`,
  );
  return res.data;
}

export async function listCompanyServices(): Promise<CompanyService[]> {
  const res = await apiClient.get<CompanyService[]>("/api/objectives/services");
  return res.data ?? [];
}

export async function createCompanyService(name: string): Promise<CompanyService> {
  const res = await apiClient.post<CompanyService>("/api/objectives/services", { name });
  return res.data;
}

export async function addMilestone(
  objectiveId: string,
  body: MilestoneCreate,
): Promise<ObjectiveMilestone> {
  const res = await apiClient.post<ObjectiveMilestone>(
    `/api/objectives/${objectiveId}/milestones`,
    body,
  );
  return res.data;
}

export async function updateMilestone(
  objectiveId: string,
  milestoneId: string,
  body: MilestoneUpdate,
): Promise<ObjectiveMilestone> {
  const res = await apiClient.put<ObjectiveMilestone>(
    `/api/objectives/${objectiveId}/milestones/${milestoneId}`,
    body,
  );
  return res.data;
}

export async function deleteMilestone(objectiveId: string, milestoneId: string): Promise<void> {
  await apiClient.delete(`/api/objectives/${objectiveId}/milestones/${milestoneId}`);
}

export async function addCheckin(
  objectiveId: string,
  body: CheckinCreate,
): Promise<ObjectiveCheckin> {
  const res = await apiClient.post<ObjectiveCheckin>(
    `/api/objectives/${objectiveId}/checkins`,
    body,
  );
  return res.data;
}
