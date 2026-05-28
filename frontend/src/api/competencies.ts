import apiClient from "./apiClient";
import { downloadBlob } from '@/lib/downloadBlob';

export type CompetencyCategory =
  | "technique"
  | "manageriale"
  | "transversale"
  | "reglementaire"
  | "securite";

export type CompetencyRef = {
  id: string;
  company_id: string;
  name: string;
  category: string;
  description?: string | null;
  required_level?: number | null;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
};

export type EmployeeCompetency = {
  id: string;
  company_id: string;
  employee_id: string;
  competency_id: string;
  score: number;
  evaluation_date: string;
  evaluated_by?: string | null;
  comment?: string | null;
  created_at?: string | null;
  competency_name?: string | null;
  competency_category?: string | null;
  required_level?: number | null;
  employee_name?: string | null;
  is_gap: boolean;
};

export type MatrixCell = {
  employee_id: string;
  employee_name: string;
  competency_id: string;
  competency_name: string;
  score: number;
  required_level?: number | null;
  is_gap: boolean;
};

export type CompetencyMatrix = {
  employees: { id: string; name: string }[];
  competencies: { id: string; name: string; category: string; required_level?: number | null }[];
  cells: MatrixCell[];
  gaps: MatrixCell[];
  gap_trainings: { competency_id: string; training_id: string; training_title: string }[];
};

export type MobilityRecommendedPosition = {
  poste: string;
  compatibilite: number;
  points_forts: string[];
  competences_a_developper: string[];
};

export type MobilityRecommendedTraining = {
  training_id?: string | null;
  titre: string;
  priorite: "Haute" | "Moyenne" | "Faible";
  competence_ciblee: string;
  impact_estime: string;
};

export type MobilityAnalysis = {
  employee_id: string;
  mobilite_score: number;
  potentiel_evolution: string;
  postes_recommandes: MobilityRecommendedPosition[];
  formations_recommandees: MobilityRecommendedTraining[];
  synthese: string;
  analyzed_at: string;
};

export type CompetencyRefCreate = {
  name: string;
  category: CompetencyCategory;
  description?: string | null;
  required_level?: number | null;
};

export type CompetencyRefUpdate = Partial<CompetencyRefCreate> & { status?: string | null };

export type EmployeeCompetencyCreate = {
  employee_id: string;
  competency_id: string;
  score: number;
  evaluation_date: string;
  comment?: string | null;
};

export async function getCompetencyRefs(includeArchived?: boolean): Promise<CompetencyRef[]> {
  const q = includeArchived ? "?include_archived=true" : "";
  const res = await apiClient.get<CompetencyRef[]>(`/api/competencies/refs${q}`);
  return res.data ?? [];
}

export async function getCompetencyRef(id: string): Promise<CompetencyRef> {
  const res = await apiClient.get<CompetencyRef>(`/api/competencies/refs/${id}`);
  return res.data;
}

export async function createCompetencyRef(data: CompetencyRefCreate): Promise<CompetencyRef> {
  const res = await apiClient.post<CompetencyRef>("/api/competencies/refs", data);
  return res.data;
}

export async function updateCompetencyRef(
  id: string,
  data: CompetencyRefUpdate,
): Promise<CompetencyRef> {
  const res = await apiClient.put<CompetencyRef>(`/api/competencies/refs/${id}`, data);
  return res.data;
}

export async function archiveCompetencyRef(id: string): Promise<void> {
  await apiClient.post(`/api/competencies/refs/${id}/archive`);
}

export async function getEvaluations(employeeId?: string): Promise<EmployeeCompetency[]> {
  const q = employeeId ? `?employee_id=${encodeURIComponent(employeeId)}` : "";
  const res = await apiClient.get<EmployeeCompetency[]>(`/api/competencies/evaluations${q}`);
  return res.data ?? [];
}

export async function evaluateEmployee(data: EmployeeCompetencyCreate): Promise<EmployeeCompetency> {
  const res = await apiClient.post<EmployeeCompetency>("/api/competencies/evaluations", data);
  return res.data;
}

export async function getMatrix(params?: {
  service_id?: string;
  category?: string;
}): Promise<CompetencyMatrix> {
  const sp = new URLSearchParams();
  if (params?.service_id) sp.set("service_id", params.service_id);
  if (params?.category) sp.set("category", params.category);
  const q = sp.toString();
  const res = await apiClient.get<CompetencyMatrix>(
    `/api/competencies/matrix${q ? `?${q}` : ""}`,
  );
  return res.data;
}

export async function exportMatrixExcel(params?: {
  service_id?: string;
  category?: string;
}): Promise<void> {
  const sp = new URLSearchParams();
  if (params?.service_id) sp.set("service_id", params.service_id);
  if (params?.category) sp.set("category", params.category);
  const q = sp.toString();
  const res = await apiClient.get<Blob>(`/api/competencies/matrix/export${q ? `?${q}` : ""}`, {
    responseType: "blob",
  });
  const cd = res.headers["content-disposition"];
  let filename = "matrice_competences.xlsx";
  if (cd && cd.includes("filename=")) {
    const m = cd.match(/filename="?([^";]+)"?/);
    if (m?.[1]) filename = m[1];
  }
  downloadBlob(res.data as Blob, filename);
}

/** Analyse mobilité IA (RH). L’entreprise active est lue via l’intercepteur (X-Active-Company). */
export async function analyzeMobility(
  employeeId: string,
  _companyId?: string,
): Promise<MobilityAnalysis> {
  const res = await apiClient.post<MobilityAnalysis>(
    `/api/competencies/employees/${encodeURIComponent(employeeId)}/analyze-mobility`,
  );
  return res.data;
}
