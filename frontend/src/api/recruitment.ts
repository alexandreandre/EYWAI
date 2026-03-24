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
  created_at: string;
  updated_at: string;
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

export async function hireCandidate(
  candidateId: string,
  body: { hire_date: string; site?: string; service?: string; job_title?: string; contract_type?: string }
): Promise<{ ok: boolean; employee_id: string; message: string }> {
  const res = await apiClient.post(`/api/recruitment/candidates/${candidateId}/hire`, body);
  return res.data;
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

export async function createNote(body: { candidate_id: string; content: string }): Promise<Note> {
  const res = await apiClient.post<Note>("/api/recruitment/notes", body);
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
