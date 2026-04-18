import apiClient from "./apiClient";

export type TrainingType =
  | "presentiel"
  | "distanciel"
  | "elearning"
  | "blended"
  | "habilitation";

export type EnrollmentStatus = "planned" | "in_progress" | "completed" | "cancelled";

export type TrainingCatalog = {
  id: string;
  company_id: string;
  title: string;
  training_type: string;
  provider?: string | null;
  duration_hours?: number | null;
  unit_cost_ht?: number | null;
  pedagogical_objective?: string | null;
  categories: string[];
  certification_id?: string | null;
  competency_id?: string | null;
  status: string;
  program_url?: string | null;
  external_link?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  certification_ref?: Record<string, unknown> | null;
  enrolled_count: number;
};

export type TrainingEnrollment = {
  id: string;
  company_id: string;
  training_id: string;
  employee_id: string;
  status: string;
  planned_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  employee_name?: string | null;
  training_title?: string | null;
  unit_cost_ht?: number | null;
  suggest_certification_creation?: boolean;
  suggested_certification_id?: string | null;
};

export type TrainingCatalogCreate = {
  title: string;
  training_type: TrainingType;
  provider?: string | null;
  duration_hours?: number | null;
  unit_cost_ht?: number | null;
  pedagogical_objective?: string | null;
  categories?: string[];
  certification_id?: string | null;
  competency_id?: string | null;
  program_url?: string | null;
  external_link?: string | null;
};

export type TrainingCatalogUpdate = Partial<TrainingCatalogCreate> & { status?: string | null };

export type TrainingEnrollmentCreate = {
  training_id: string;
  employee_id: string;
  status?: EnrollmentStatus;
  planned_date?: string | null;
  notes?: string | null;
};

export type TrainingEnrollmentUpdate = {
  status?: EnrollmentStatus;
  planned_date?: string | null;
  completion_date?: string | null;
  notes?: string | null;
};

export type TotalConsumedResponse = { year: number; total_ht: number };

export async function getTrainings(includeArchived?: boolean): Promise<TrainingCatalog[]> {
  const q = includeArchived ? "?include_archived=true" : "";
  const res = await apiClient.get<TrainingCatalog[]>(`/api/training/catalog${q}`);
  return res.data ?? [];
}

export async function getTraining(id: string): Promise<TrainingCatalog> {
  const res = await apiClient.get<TrainingCatalog>(`/api/training/catalog/${id}`);
  return res.data;
}

export async function createTraining(body: TrainingCatalogCreate): Promise<TrainingCatalog> {
  const res = await apiClient.post<TrainingCatalog>("/api/training/catalog", body);
  return res.data;
}

export async function updateTraining(id: string, body: TrainingCatalogUpdate): Promise<TrainingCatalog> {
  const res = await apiClient.put<TrainingCatalog>(`/api/training/catalog/${id}`, body);
  return res.data;
}

export async function archiveTraining(id: string): Promise<void> {
  await apiClient.post(`/api/training/catalog/${id}/archive`);
}

export async function getEnrollments(params?: {
  training_id?: string;
  employee_id?: string;
  status?: string;
}): Promise<TrainingEnrollment[]> {
  const sp = new URLSearchParams();
  if (params?.training_id) sp.set("training_id", params.training_id);
  if (params?.employee_id) sp.set("employee_id", params.employee_id);
  if (params?.status) sp.set("status", params.status);
  const q = sp.toString();
  const res = await apiClient.get<TrainingEnrollment[]>(
    `/api/training/enrollments${q ? `?${q}` : ""}`,
  );
  return res.data ?? [];
}

export async function getEnrollment(id: string): Promise<TrainingEnrollment> {
  const res = await apiClient.get<TrainingEnrollment>(`/api/training/enrollments/${id}`);
  return res.data;
}

export async function createEnrollment(body: TrainingEnrollmentCreate): Promise<TrainingEnrollment> {
  const res = await apiClient.post<TrainingEnrollment>("/api/training/enrollments", body);
  return res.data;
}

export async function updateEnrollment(
  id: string,
  body: TrainingEnrollmentUpdate,
): Promise<TrainingEnrollment> {
  const res = await apiClient.put<TrainingEnrollment>(`/api/training/enrollments/${id}`, body);
  return res.data;
}

export async function cancelEnrollment(id: string): Promise<void> {
  await apiClient.post(`/api/training/enrollments/${id}/cancel`);
}

export async function getTotalConsumed(year: number): Promise<TotalConsumedResponse> {
  const res = await apiClient.get<TotalConsumedResponse>(`/api/training/consumed/${year}`);
  return res.data;
}
