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
  requested_by?: string | null;
  manager_id?: string | null;
  manager_approved_at?: string | null;
  manager_rejected_at?: string | null;
  manager_rejection_reason?: string | null;
  rh_approved_at?: string | null;
  rh_rejected_at?: string | null;
  rh_rejection_reason?: string | null;
  manager_display_name?: string | null;
  rating?: number | null;
  evaluation_comment?: string | null;
  evaluated_at?: string | null;
  certificate_url?: string | null;
  certificate_uploaded_at?: string | null;
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

export type EnrollmentRequestBySalarie = {
  training_id: string;
  preferred_date?: string;
  motivation?: string;
};

export type ManagerApprovalRequest = {
  approved: boolean;
  rejection_reason?: string;
};

export type RHApprovalRequest = {
  approved: boolean;
  rejection_reason?: string;
  planned_start_date?: string;
  planned_end_date?: string;
};

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

/** `companyId` réservé à l’alignement API (l’entreprise active est envoyée via X-Active-Company). */
export async function requestEnrollment(
  companyId: string,
  data: EnrollmentRequestBySalarie,
): Promise<TrainingEnrollment> {
  void companyId;
  const res = await apiClient.post<TrainingEnrollment>("/api/training/enrollments/request", data);
  return res.data;
}

export async function managerApprove(
  enrollmentId: string,
  companyId: string,
  data: ManagerApprovalRequest,
): Promise<TrainingEnrollment> {
  void companyId;
  const res = await apiClient.post<TrainingEnrollment>(
    `/api/training/enrollments/${enrollmentId}/manager-approve`,
    data,
  );
  return res.data;
}

export async function rhApprove(
  enrollmentId: string,
  companyId: string,
  data: RHApprovalRequest,
): Promise<TrainingEnrollment> {
  void companyId;
  const res = await apiClient.post<TrainingEnrollment>(
    `/api/training/enrollments/${enrollmentId}/rh-approve`,
    data,
  );
  return res.data;
}

export async function getPendingManagerApproval(companyId: string): Promise<TrainingEnrollment[]> {
  void companyId;
  const res = await apiClient.get<TrainingEnrollment[]>(
    "/api/training/enrollments/pending-manager-approval",
  );
  return res.data ?? [];
}

export async function getPendingRHApproval(companyId: string): Promise<TrainingEnrollment[]> {
  void companyId;
  const res = await apiClient.get<TrainingEnrollment[]>(
    "/api/training/enrollments/pending-rh-approval",
  );
  return res.data ?? [];
}

export type TrainingEvaluationRequest = {
  rating: number;
  comment?: string;
};

export type EvaluationSummary = {
  training_id: string;
  training_title: string;
  nb_evaluations: number;
  avg_rating: number;
  ratings_distribution: Record<string, number>;
};

export async function submitEvaluation(
  enrollmentId: string,
  companyId: string,
  data: TrainingEvaluationRequest,
): Promise<TrainingEnrollment> {
  void companyId;
  const res = await apiClient.post<TrainingEnrollment>(
    `/api/training/enrollments/${enrollmentId}/evaluate`,
    data,
  );
  return res.data;
}

export async function uploadEnrollmentCertificate(
  enrollmentId: string,
  companyId: string,
  file: File,
): Promise<{ certificate_url: string }> {
  void companyId;
  const fd = new FormData();
  fd.append("file", file);
  const res = await apiClient.post<{ certificate_url: string }>(
    `/api/training/enrollments/${enrollmentId}/upload-certificate`,
    fd,
  );
  return res.data;
}

export async function getEvaluationsSummary(companyId: string): Promise<EvaluationSummary[]> {
  void companyId;
  const res = await apiClient.get<EvaluationSummary[]>(`/api/training/evaluations/summary`);
  return res.data ?? [];
}
