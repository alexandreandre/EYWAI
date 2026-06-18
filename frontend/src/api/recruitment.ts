/**
 * API client for the Recruitment (ATS) module.
 */

import apiClient from "./apiClient";

// ─── Types ──────────────────────────────────────────────────────────

export interface Job {
  id: string;
  company_id: string;
  title: string;
  description?: string | null;
  location?: string | null;
  contract_type?: string | null;
  status: "draft" | "active" | "archived";
  tags?: string[] | null;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
  candidate_count?: number;
}

export interface PipelineStage {
  id: string;
  job_id: string;
  name: string;
  position: number;
  is_final: boolean;
  stage_type: "standard" | "rejected" | "hired";
}

export interface Candidate {
  id: string;
  company_id: string;
  job_id: string;
  current_stage_id?: string | null;
  current_stage_name?: string | null;
  current_stage_type?: string | null;
  first_name: string;
  last_name: string;
  email?: string | null;
  phone?: string | null;
  source?: string | null;
  rejection_reason?: string | null;
  rejection_reason_detail?: string | null;
  hired_at?: string | null;
  employee_id?: string | null;
  /** URL du CV si le backend / stockage l’expose */
  cv_url?: string | null;
  ai_score?: number | null;
  ai_scored_at?: string | null;
  created_at: string;
  updated_at: string;
}

/**
 * Candidats "à traiter" côté RH :
 * tout ce qui n'est ni embauché ni rejeté.
 */
export function countActionableCandidates(candidates: Candidate[]): number {
  return candidates.filter((c) => {
    const stageType = (c.current_stage_type || "").toLowerCase();
    return stageType !== "hired" && stageType !== "rejected";
  }).length;
}

/**
 * Priorité recrutement du dashboard/sidebar :
 * uniquement les candidats présents dans la vignette "Entretien RH".
 */
export function isRecruitmentPriorityCandidate(candidate: Candidate): boolean {
  const stageName = (candidate.current_stage_name || "").toLowerCase().trim();
  return stageName.includes("entretien rh");
}

export function countRecruitmentPriorityCandidates(candidates: Candidate[]): number {
  return candidates.filter(isRecruitmentPriorityCandidate).length;
}

export interface Interview {
  id: string;
  candidate_id: string;
  interview_type: string;
  scheduled_at: string;
  duration_minutes: number;
  location?: string | null;
  meeting_link?: string | null;
  status: "planned" | "completed" | "cancelled";
  summary?: string | null;
  created_by?: string | null;
  created_at: string;
  participants?: {
    user_id: string;
    role: string;
    first_name?: string | null;
    last_name?: string | null;
  }[];
}

export interface Note {
  id: string;
  candidate_id: string;
  content: string;
  author_id: string;
  author_first_name?: string | null;
  author_last_name?: string | null;
  created_at: string;
  audio_url?: string | null;
}

export interface Opinion {
  id: string;
  candidate_id: string;
  rating: "favorable" | "defavorable";
  comment?: string | null;
  author_id: string;
  author_first_name?: string | null;
  author_last_name?: string | null;
  created_at: string;
}

export interface TimelineEvent {
  id: string;
  candidate_id: string;
  event_type: string;
  description: string;
  metadata?: Record<string, unknown> | null;
  actor_id?: string | null;
  actor_first_name?: string | null;
  actor_last_name?: string | null;
  created_at: string;
}

export interface DuplicateWarning {
  type: "candidate" | "employee";
  existing_id: string;
  first_name?: string | null;
  last_name?: string | null;
  email?: string | null;
}

// ─── Settings ───────────────────────────────────────────────────────

export async function getRecruitmentSettings(): Promise<{ enabled: boolean }> {
  const res = await apiClient.get<{ enabled: boolean }>("/api/recruitment/settings");
  return res.data;
}

// ─── Jobs ───────────────────────────────────────────────────────────

export async function getJobs(status?: string): Promise<Job[]> {
  const params = status ? `?status=${status}` : "";
  const res = await apiClient.get<Job[]>(`/api/recruitment/jobs${params}`);
  return res.data ?? [];
}

export async function createJob(body: {
  title: string;
  description?: string;
  location?: string;
  contract_type?: string;
  status?: string;
  tags?: string[];
}): Promise<Job> {
  const res = await apiClient.post<Job>("/api/recruitment/jobs", body);
  return res.data;
}

export async function updateJob(
  jobId: string,
  body: Partial<Pick<Job, "title" | "description" | "location" | "contract_type" | "status" | "tags">>
): Promise<Job> {
  const res = await apiClient.patch<Job>(`/api/recruitment/jobs/${jobId}`, body);
  return res.data;
}

// ─── Pipeline Stages ────────────────────────────────────────────────

export async function getPipelineStages(jobId: string): Promise<PipelineStage[]> {
  const res = await apiClient.get<PipelineStage[]>(`/api/recruitment/jobs/${jobId}/stages`);
  return res.data ?? [];
}

export async function createPipelineStage(
  jobId: string,
  body: { name: string }
): Promise<PipelineStage> {
  const res = await apiClient.post<PipelineStage>(`/api/recruitment/jobs/${jobId}/stages`, body);
  return res.data;
}

export async function updatePipelineStage(
  jobId: string,
  stageId: string,
  body: { name?: string; is_final?: boolean }
): Promise<PipelineStage> {
  const res = await apiClient.patch<PipelineStage>(
    `/api/recruitment/jobs/${jobId}/stages/${stageId}`,
    body
  );
  return res.data;
}

export async function deletePipelineStage(jobId: string, stageId: string): Promise<void> {
  await apiClient.delete(`/api/recruitment/jobs/${jobId}/stages/${stageId}`);
}

export async function reorderPipelineStages(
  jobId: string,
  stageIds: string[]
): Promise<PipelineStage[]> {
  const res = await apiClient.post<PipelineStage[]>(
    `/api/recruitment/jobs/${jobId}/stages/reorder`,
    { stage_ids: stageIds }
  );
  return res.data ?? [];
}

// ─── Candidates ─────────────────────────────────────────────────────

export async function getCandidates(params?: {
  job_id?: string;
  stage_id?: string;
  search?: string;
}): Promise<Candidate[]> {
  const sp = new URLSearchParams();
  if (params?.job_id) sp.set("job_id", params.job_id);
  if (params?.stage_id) sp.set("stage_id", params.stage_id);
  if (params?.search) sp.set("search", params.search);
  const q = sp.toString();
  const res = await apiClient.get<Candidate[]>(`/api/recruitment/candidates${q ? `?${q}` : ""}`);
  return res.data ?? [];
}

export async function getCandidate(candidateId: string): Promise<Candidate> {
  const res = await apiClient.get<Candidate>(`/api/recruitment/candidates/${candidateId}`);
  return res.data;
}

export async function createCandidate(body: {
  job_id: string;
  first_name: string;
  last_name: string;
  email?: string;
  phone?: string;
  source?: string;
}): Promise<Candidate> {
  const res = await apiClient.post<Candidate>("/api/recruitment/candidates", body);
  return res.data;
}

export async function updateCandidate(
  candidateId: string,
  body: Partial<Pick<Candidate, "first_name" | "last_name" | "email" | "phone" | "source">>
): Promise<Candidate> {
  const res = await apiClient.patch<Candidate>(`/api/recruitment/candidates/${candidateId}`, body);
  return res.data;
}

export async function deleteCandidate(candidateId: string): Promise<void> {
  await apiClient.delete(`/api/recruitment/candidates/${candidateId}`);
}

export async function moveCandidate(
  candidateId: string,
  body: { stage_id: string; rejection_reason?: string; rejection_reason_detail?: string }
): Promise<{ ok: boolean; stage: PipelineStage }> {
  const res = await apiClient.post(`/api/recruitment/candidates/${candidateId}/move`, body);
  return res.data;
}

export async function checkDuplicate(candidateId: string): Promise<{ warnings: DuplicateWarning[] }> {
  const res = await apiClient.post(`/api/recruitment/candidates/${candidateId}/check-duplicate`);
  return res.data;
}

export interface HireResult {
  ok: boolean;
  employee_id?: string;
  username?: string;
  email?: string;
  generated_password?: string;
  credentials_pdf_path?: string;
  message?: string;
  requires_confirmation?: boolean;
  existing_employee_id?: string;
  existing_employee_first_name?: string;
  existing_employee_last_name?: string;
  existing_employee_email?: string;
}

export async function hireCandidate(
  candidateId: string,
  body: {
    hire_date: string;
    site?: string;
    service?: string;
    job_title?: string;
    contract_type?: string;
    statut?: string;
    contract_end_date?: string;
    date_debut_execution?: string;
    date_conclusion_contrat?: string;
    maintien_regime_apprenti?: boolean;
    link_to_employee_id?: string;
    skip_duplicate_check?: boolean;
  }
): Promise<HireResult> {
  const res = await apiClient.post(`/api/recruitment/candidates/${candidateId}/hire`, body);
  return res.data;
}

export async function uploadCandidateCV(
  candidateId: string,
  companyId: string,
  file: File
): Promise<{ cv_url: string }> {
  const formData = new FormData();
  formData.append("file", file);
  const res = await apiClient.post<{ cv_url: string }>(
    `/api/recruitment/candidates/${candidateId}/upload-cv`,
    formData,
    {
      headers: {
        "X-Active-Company": companyId,
      },
    }
  );
  return res.data;
}

export type ScoringMention = "Excellent" | "Bon" | "Moyen" | "Faible";
export type ScoringConfiance = "Haute" | "Moyenne" | "Faible";

export interface ScoringResult {
  candidate_id: string;
  score: number;
  mention: ScoringMention | string;
  confiance?: ScoringConfiance | string | null;
  points_forts: string[];
  points_faibles: string[];
  limites?: string | null;
  recommandation: string;
  scored_at: string;
}

export async function scoreCandidateAI(
  candidateId: string,
  companyId: string
): Promise<ScoringResult> {
  const res = await apiClient.post<ScoringResult>(
    `/api/recruitment/candidates/${candidateId}/score`,
    {},
    {
      headers: { "X-Active-Company": companyId },
    }
  );
  return res.data;
}

export async function getCandidateScore(
  candidateId: string,
  companyId: string
): Promise<ScoringResult> {
  const res = await apiClient.get<ScoringResult>(
    `/api/recruitment/candidates/${candidateId}/score`,
    {
      headers: { "X-Active-Company": companyId },
    }
  );
  return res.data;
}

export async function archiveCandidate(candidateId: string): Promise<void> {
  await apiClient.post(`/api/recruitment/candidates/${candidateId}/archive`, {});
}

// ─── Interviews ─────────────────────────────────────────────────────

export async function getInterviews(candidateId?: string): Promise<Interview[]> {
  const params = candidateId ? `?candidate_id=${candidateId}` : "";
  const res = await apiClient.get<Interview[]>(`/api/recruitment/interviews${params}`);
  return res.data ?? [];
}

export async function createInterview(body: {
  candidate_id: string;
  interview_type?: string;
  scheduled_at: string;
  duration_minutes?: number;
  location?: string;
  meeting_link?: string;
  participant_user_ids?: string[];
}): Promise<Interview> {
  const res = await apiClient.post<Interview>("/api/recruitment/interviews", body);
  return res.data;
}

export async function updateInterview(
  interviewId: string,
  body: Partial<Pick<Interview, "interview_type" | "scheduled_at" | "duration_minutes" | "location" | "meeting_link" | "status" | "summary">>
): Promise<void> {
  await apiClient.patch(`/api/recruitment/interviews/${interviewId}`, body);
}

// ─── Notes ──────────────────────────────────────────────────────────

export async function getNotes(candidateId: string): Promise<Note[]> {
  const res = await apiClient.get<Note[]>(`/api/recruitment/notes?candidate_id=${candidateId}`);
  return res.data ?? [];
}

export async function createNote(body: {
  candidate_id: string;
  content: string;
  audio_url?: string | null;
}): Promise<Note> {
  const res = await apiClient.post<Note>("/api/recruitment/notes", body);
  return res.data;
}

export async function uploadNoteAudio(
  candidateId: string,
  companyId: string,
  blob: Blob
): Promise<{ audio_url: string }> {
  const ext =
    blob.type.includes("ogg") ? "ogg" : blob.type.includes("mp4") ? "m4a" : "webm";
  const formData = new FormData();
  formData.append("file", blob, `note.${ext}`);
  const res = await apiClient.post<{ audio_url: string }>(
    `/api/recruitment/notes/upload-audio?candidate_id=${encodeURIComponent(candidateId)}`,
    formData,
    {
      headers: { "X-Active-Company": companyId },
    }
  );
  return res.data;
}

// ─── Opinions ───────────────────────────────────────────────────────

export async function getOpinions(candidateId: string): Promise<Opinion[]> {
  const res = await apiClient.get<Opinion[]>(`/api/recruitment/opinions?candidate_id=${candidateId}`);
  return res.data ?? [];
}

export async function createOpinion(body: {
  candidate_id: string;
  rating: "favorable" | "defavorable";
  comment?: string;
}): Promise<Opinion> {
  const res = await apiClient.post<Opinion>("/api/recruitment/opinions", body);
  return res.data;
}

// ─── Timeline ───────────────────────────────────────────────────────

export async function getTimeline(candidateId: string): Promise<TimelineEvent[]> {
  const res = await apiClient.get<TimelineEvent[]>(`/api/recruitment/timeline?candidate_id=${candidateId}`);
  return res.data ?? [];
}

// ─── Rejection Reasons ──────────────────────────────────────────────

export async function getRejectionReasons(): Promise<{ reasons: string[] }> {
  const res = await apiClient.get<{ reasons: string[] }>("/api/recruitment/rejection-reasons");
  return res.data;
}

// ─── Analytics ──────────────────────────────────────────────────────

export interface TimeToHireStats {
  job_id: string;
  job_title: string;
  avg_days: number;
  min_days: number;
  max_days: number;
  nb_hired: number;
}

export interface SourceStats {
  source: string;
  nb_candidates: number;
  nb_hired: number;
  conversion_rate: number;
}

export interface StageConversionStats {
  stage_name: string;
  stage_position: number;
  nb_candidates: number;
  nb_passed: number;
  conversion_rate: number;
  avg_days_in_stage: number;
}

export interface RecruitmentAnalytics {
  period_start: string | null;
  period_end: string | null;
  total_candidates: number;
  total_hired: number;
  overall_conversion_rate: number;
  avg_time_to_hire_days: number;
  time_to_hire_by_job: TimeToHireStats[];
  source_stats: SourceStats[];
  stage_conversion: StageConversionStats[];
  cost_per_hire: number | null;
}

export interface RecruitmentAnalyticsParams {
  job_id?: string;
  date_from?: string;
  date_to?: string;
  budget_total?: number;
}

export async function getRecruitmentAnalytics(
  companyId: string,
  params?: RecruitmentAnalyticsParams
): Promise<RecruitmentAnalytics> {
  const sp = new URLSearchParams();
  if (params?.job_id) sp.set("job_id", params.job_id);
  if (params?.date_from) sp.set("date_from", params.date_from);
  if (params?.date_to) sp.set("date_to", params.date_to);
  if (params?.budget_total != null && !Number.isNaN(params.budget_total)) {
    sp.set("budget_total", String(params.budget_total));
  }
  const q = sp.toString();
  const res = await apiClient.get<RecruitmentAnalytics>(
    `/api/recruitment/analytics${q ? `?${q}` : ""}`,
    { headers: { "X-Active-Company": companyId } }
  );
  return res.data;
}

export async function downloadJobFichePostePdf(
  jobId: string,
  templateId?: string | null
): Promise<Blob> {
  const res = await apiClient.post(
    `/api/recruitment/jobs/${jobId}/fiche-poste`,
    templateId ? { template_id: templateId } : {},
    { responseType: 'blob' }
  );
  return res.data;
}
