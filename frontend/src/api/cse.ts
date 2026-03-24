// frontend/src/api/cse.ts
// API pour le module CSE & Dialogue Social

import apiClient from "./apiClient";

// ============================================================================
// Types
// ============================================================================

export type ElectedMemberRole = "titulaire" | "suppleant" | "secretaire" | "tresorier" | "autre";
export type MeetingType = "ordinaire" | "extraordinaire" | "cssct" | "autre";
export type MeetingStatus = "a_venir" | "en_cours" | "terminee";
export type RecordingStatus = "not_started" | "in_progress" | "completed" | "failed";
export type ParticipantRole = "participant" | "observateur";
export type BDESDocumentType = "bdes" | "pv" | "autre";
export type ElectionCycleStatus = "in_progress" | "completed";
export type TimelineStepStatus = "pending" | "completed" | "overdue";

// ============================================================================
// Interfaces - Élus CSE
// ============================================================================

export interface ElectedMember {
  id: string;
  company_id: string;
  employee_id: string;
  role: ElectedMemberRole;
  college: string | null;
  start_date: string;
  end_date: string;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
  first_name?: string | null;
  last_name?: string | null;
  job_title?: string | null;
}

export interface ElectedMemberListItem {
  id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  job_title: string | null;
  role: ElectedMemberRole;
  college: string | null;
  start_date: string;
  end_date: string;
  is_active: boolean;
  days_remaining: number | null;
}

export interface ElectedMemberCreate {
  employee_id: string;
  role: ElectedMemberRole;
  college?: string | null;
  start_date: string;
  end_date: string;
  notes?: string | null;
}

export interface ElectedMemberUpdate {
  role?: ElectedMemberRole;
  college?: string | null;
  start_date?: string;
  end_date?: string;
  is_active?: boolean;
  notes?: string | null;
}

export interface ElectedMemberStatus {
  is_elected: boolean;
  current_mandate: ElectedMember | null;
  role: ElectedMemberRole | null;
}

export interface MandateAlert {
  elected_member_id: string;
  employee_id: string;
  first_name: string;
  last_name: string;
  role: ElectedMemberRole;
  end_date: string;
  days_remaining: number;
  months_remaining: number;
}

// ============================================================================
// Interfaces - Réunions CSE
// ============================================================================

export interface Meeting {
  id: string;
  company_id: string;
  title: string;
  meeting_date: string;
  meeting_time: string | null;
  location: string | null;
  meeting_type: MeetingType;
  status: MeetingStatus;
  agenda: Record<string, any> | null;
  notes: Record<string, any> | null;
  convocations_pdf_path: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  participants?: MeetingParticipant[];
  participant_count?: number;
  recording_status?: RecordingStatus;
}

export interface MeetingListItem {
  id: string;
  title: string;
  meeting_date: string;
  meeting_time: string | null;
  meeting_type: MeetingType;
  status: MeetingStatus;
  participant_count: number;
  created_at: string;
}

export interface MeetingCreate {
  title: string;
  meeting_date: string;
  meeting_time?: string | null;
  location?: string | null;
  meeting_type: MeetingType;
  agenda?: Record<string, any> | null;
  notes?: Record<string, any> | null;
  participant_ids?: string[];
}

export interface MeetingUpdate {
  title?: string;
  meeting_date?: string;
  meeting_time?: string | null;
  location?: string | null;
  meeting_type?: MeetingType;
  status?: MeetingStatus;
  agenda?: Record<string, any> | null;
  notes?: Record<string, any> | null;
}

export interface MeetingParticipant {
  meeting_id: string;
  employee_id: string;
  role: ParticipantRole;
  invited_at: string | null;
  confirmed_at: string | null;
  attended: boolean;
  first_name?: string | null;
  last_name?: string | null;
  job_title?: string | null;
}

export interface MeetingParticipantAdd {
  employee_ids: string[];
  role?: ParticipantRole;
}

// ============================================================================
// Interfaces - Enregistrements
// ============================================================================

export interface RecordingConsent {
  employee_id: string;
  consent_given: boolean;
  timestamp?: string | null;
}

export interface RecordingStart {
  consents: RecordingConsent[];
}

export interface RecordingStatusRead {
  meeting_id: string;
  status: RecordingStatus;
  recording_started_at: string | null;
  recording_ended_at: string | null;
  consent_given_by: Array<{ employee_id: string; timestamp: string }>;
  error_message: string | null;
  has_transcription: boolean;
  has_summary: boolean;
  has_minutes: boolean;
}

// ============================================================================
// Interfaces - Heures de délégation
// ============================================================================

export interface DelegationHour {
  id: string;
  company_id: string;
  employee_id: string;
  date: string;
  duration_hours: number;
  reason: string;
  meeting_id: string | null;
  created_by: string | null;
  created_at: string;
  first_name?: string | null;
  last_name?: string | null;
}

export interface DelegationHourCreate {
  employee_id?: string | null;
  date: string;
  duration_hours: number;
  reason: string;
  meeting_id?: string | null;
}

export interface DelegationQuota {
  id: string;
  company_id: string;
  collective_agreement_id: string | null;
  quota_hours_per_month: number;
  notes: string | null;
  collective_agreement_name?: string | null;
}

export interface DelegationQuotaCreate {
  collective_agreement_id?: string | null;
  quota_hours_per_month: number;
  notes?: string | null;
}

export interface DelegationSummary {
  employee_id: string;
  first_name: string;
  last_name: string;
  quota_hours_per_month: number;
  consumed_hours: number;
  remaining_hours: number;
  period_start: string;
  period_end: string;
}

// ============================================================================
// Interfaces - Documents BDES
// ============================================================================

export interface BDESDocument {
  id: string;
  company_id: string;
  title: string;
  document_type: BDESDocumentType;
  file_path: string;
  year: number | null;
  published_at: string | null;
  published_by: string | null;
  is_visible_to_elected: boolean;
  description: string | null;
  created_at: string;
  updated_at: string;
  published_by_name?: string | null;
  download_url?: string | null;
}

export interface BDESDocumentCreate {
  title: string;
  document_type: BDESDocumentType;
  file_path: string;
  year?: number | null;
  is_visible_to_elected?: boolean;
  description?: string | null;
}

// ============================================================================
// Interfaces - Calendrier électoral
// ============================================================================

export interface ElectionCycle {
  id: string;
  company_id: string;
  cycle_name: string;
  mandate_end_date: string;
  election_date: string | null;
  status: ElectionCycleStatus;
  results_pdf_path: string | null;
  minutes_pdf_path: string | null;
  notes: Record<string, any> | null;
  created_at: string;
  updated_at: string;
  timeline?: ElectionTimelineStep[];
  days_until_mandate_end?: number | null;
}

export interface ElectionCycleCreate {
  cycle_name: string;
  mandate_end_date: string;
  election_date?: string | null;
  notes?: Record<string, any> | null;
}

export interface ElectionTimelineStep {
  id: string;
  election_cycle_id: string;
  step_name: string;
  step_order: number;
  due_date: string;
  completed_at: string | null;
  status: TimelineStepStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ElectionAlert {
  cycle_id: string;
  cycle_name: string;
  mandate_end_date: string;
  days_remaining: number;
  alert_level: "info" | "warning" | "critical";
  message: string;
}

// ============================================================================
// API Functions - Élus CSE
// ============================================================================

export async function getElectedMembers(activeOnly: boolean = true): Promise<ElectedMemberListItem[]> {
  const response = await apiClient.get("/api/cse/elected-members", {
    params: { active_only: activeOnly },
  });
  return response.data;
}

export async function createElectedMember(data: ElectedMemberCreate): Promise<ElectedMember> {
  const response = await apiClient.post("/api/cse/elected-members", data);
  return response.data;
}

export async function updateElectedMember(
  memberId: string,
  data: ElectedMemberUpdate
): Promise<ElectedMember> {
  const response = await apiClient.put(`/api/cse/elected-members/${memberId}`, data);
  return response.data;
}

export async function deleteElectedMember(memberId: string): Promise<void> {
  await apiClient.delete(`/api/cse/elected-members/${memberId}`);
}

export async function getMandateAlerts(monthsBefore: number = 3): Promise<MandateAlert[]> {
  const response = await apiClient.get("/api/cse/elected-members/alerts", {
    params: { months_before: monthsBefore },
  });
  return response.data;
}

export async function getMyElectedStatus(): Promise<ElectedMemberStatus> {
  const response = await apiClient.get("/api/cse/elected-members/me");
  return response.data;
}

// ============================================================================
// API Functions - Réunions CSE
// ============================================================================

export async function getMeetings(
  status?: MeetingStatus,
  meetingType?: MeetingType
): Promise<MeetingListItem[]> {
  const params: Record<string, any> = {};
  if (status) params.status = status;
  if (meetingType) params.meeting_type = meetingType;
  
  const response = await apiClient.get("/api/cse/meetings", { params });
  return response.data;
}

export async function createMeeting(data: MeetingCreate): Promise<Meeting> {
  const response = await apiClient.post("/api/cse/meetings", data);
  return response.data;
}

export async function getMeetingById(meetingId: string): Promise<Meeting> {
  const response = await apiClient.get(`/api/cse/meetings/${meetingId}`);
  return response.data;
}

export async function updateMeeting(
  meetingId: string,
  data: MeetingUpdate
): Promise<Meeting> {
  const response = await apiClient.put(`/api/cse/meetings/${meetingId}`, data);
  return response.data;
}

export async function addMeetingParticipants(
  meetingId: string,
  data: MeetingParticipantAdd
): Promise<MeetingParticipant[]> {
  const response = await apiClient.post(`/api/cse/meetings/${meetingId}/participants`, data);
  return response.data;
}

export async function removeMeetingParticipant(
  meetingId: string,
  employeeId: string
): Promise<void> {
  await apiClient.delete(`/api/cse/meetings/${meetingId}/participants/${employeeId}`);
}

export async function updateMeetingStatus(
  meetingId: string,
  status: MeetingStatus
): Promise<Meeting> {
  const response = await apiClient.put(`/api/cse/meetings/${meetingId}/status`, null, {
    params: { status },
  });
  return response.data;
}

// ============================================================================
// API Functions - Enregistrements
// ============================================================================

export async function startRecording(
  meetingId: string,
  data: RecordingStart
): Promise<RecordingStatusRead> {
  const response = await apiClient.post(`/api/cse/meetings/${meetingId}/recording/start`, data);
  return response.data;
}

export async function stopRecording(meetingId: string): Promise<RecordingStatusRead> {
  const response = await apiClient.post(`/api/cse/meetings/${meetingId}/recording/stop`);
  return response.data;
}

export async function getRecordingStatus(meetingId: string): Promise<RecordingStatusRead> {
  const response = await apiClient.get(`/api/cse/meetings/${meetingId}/recording/status`);
  return response.data;
}

export async function processRecording(meetingId: string): Promise<any> {
  const response = await apiClient.post(`/api/cse/meetings/${meetingId}/recording/process`);
  return response.data;
}

// ============================================================================
// API Functions - Heures de délégation
// ============================================================================

export async function getDelegationQuota(
  employeeId?: string
): Promise<DelegationQuota | null> {
  const params: Record<string, any> = {};
  if (employeeId) params.employee_id = employeeId;
  
  const response = await apiClient.get("/api/cse/delegation/quota", { params });
  return response.data;
}

export async function getDelegationHours(
  employeeId?: string,
  periodStart?: string,
  periodEnd?: string
): Promise<DelegationHour[]> {
  const params: Record<string, any> = {};
  if (employeeId) params.employee_id = employeeId;
  if (periodStart) params.period_start = periodStart;
  if (periodEnd) params.period_end = periodEnd;
  
  const response = await apiClient.get("/api/cse/delegation/hours", { params });
  return response.data;
}

export async function createDelegationHour(data: DelegationHourCreate): Promise<DelegationHour> {
  const response = await apiClient.post("/api/cse/delegation/hours", data);
  return response.data;
}

export async function getDelegationSummary(
  periodStart: string,
  periodEnd: string
): Promise<DelegationSummary[]> {
  const response = await apiClient.get("/api/cse/delegation/summary", {
    params: { period_start: periodStart, period_end: periodEnd },
  });
  return response.data;
}

export async function getDelegationQuotas(): Promise<DelegationQuota[]> {
  const response = await apiClient.get("/api/cse/delegation/quotas");
  return response.data;
}

// ============================================================================
// API Functions - Documents BDES
// ============================================================================

export async function getBDESDocuments(
  year?: number,
  documentType?: BDESDocumentType
): Promise<BDESDocument[]> {
  const params: Record<string, any> = {};
  if (year) params.year = year;
  if (documentType) params.document_type = documentType;
  
  const response = await apiClient.get("/api/cse/bdes-documents", { params });
  return response.data;
}

export async function uploadBDESDocument(
  file: File,
  data: Omit<BDESDocumentCreate, "file_path">
): Promise<BDESDocument> {
  const formData = new FormData();
  formData.append("file", file);
  formData.append("title", data.title);
  formData.append("document_type", data.document_type);
  if (data.year) formData.append("year", data.year.toString());
  formData.append("is_visible_to_elected", data.is_visible_to_elected?.toString() ?? "true");
  if (data.description) formData.append("description", data.description);
  
  const response = await apiClient.post("/api/cse/bdes-documents", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data;
}

export async function downloadBDESDocument(documentId: string): Promise<string> {
  const response = await apiClient.get(`/api/cse/bdes-documents/${documentId}/download`);
  return response.data.download_url;
}

// ============================================================================
// API Functions - Calendrier électoral
// ============================================================================

export async function getElectionCycles(): Promise<ElectionCycle[]> {
  const response = await apiClient.get("/api/cse/election-cycles");
  return response.data;
}

export async function createElectionCycle(data: ElectionCycleCreate): Promise<ElectionCycle> {
  const response = await apiClient.post("/api/cse/election-cycles", data);
  return response.data;
}

export async function getElectionCycleById(cycleId: string): Promise<ElectionCycle> {
  const response = await apiClient.get(`/api/cse/election-cycles/${cycleId}`);
  return response.data;
}

export async function getElectionAlerts(): Promise<ElectionAlert[]> {
  const response = await apiClient.get("/api/cse/election-cycles/alerts");
  return response.data;
}

// ============================================================================
// API Functions - Exports
// ============================================================================

export async function exportElectedMembers(): Promise<Blob> {
  const response = await apiClient.get("/api/cse/exports/elected-members", {
    responseType: "blob",
  });
  return response.data;
}

export async function exportDelegationHours(
  periodStart?: string,
  periodEnd?: string
): Promise<Blob> {
  const params: Record<string, any> = {};
  if (periodStart) params.period_start = periodStart;
  if (periodEnd) params.period_end = periodEnd;
  
  const response = await apiClient.get("/api/cse/exports/delegation-hours", {
    params,
    responseType: "blob",
  });
  return response.data;
}

export async function exportMeetingsHistory(
  periodStart?: string,
  periodEnd?: string
): Promise<Blob> {
  const params: Record<string, any> = {};
  if (periodStart) params.period_start = periodStart;
  if (periodEnd) params.period_end = periodEnd;
  
  const response = await apiClient.get("/api/cse/exports/meetings-history", {
    params,
    responseType: "blob",
  });
  return response.data;
}

export async function exportMinutesAnnual(year: number): Promise<Blob> {
  const response = await apiClient.get("/api/cse/exports/minutes-annual", {
    params: { year },
    responseType: "blob",
  });
  return response.data;
}

export async function exportElectionCalendar(cycleId?: string): Promise<Blob> {
  const params: Record<string, any> = {};
  if (cycleId) params.cycle_id = cycleId;
  
  const response = await apiClient.get("/api/cse/exports/election-calendar", {
    params,
    responseType: "blob",
  });
  return response.data;
}
