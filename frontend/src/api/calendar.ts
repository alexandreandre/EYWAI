// src/api/calendar.ts

import apiClient from './apiClient';

// --- INTERFACES POUR LE CALENDRIER ---
// Ces types décrivent la forme des données échangées avec l'API.
// Ils correspondent exactement aux modèles Pydantic du backend.

export interface PlannedEventData {
  jour: number;
  type: string;
  heures_prevues: number | null;
  /**
   * Marqueur de provenance posé par le serveur sur un jour issu d'une
   * absence validée (`origine === 'absence'`). Jamais envoyé par le client ;
   * peut être absent tant que le backend ne l'expose pas en lecture.
   */
  origine?: string | null;
}

export interface ActualHoursData {
  jour: number;
  type: string | null;
  heures_faites: number | null;
}

// --- FONCTIONS D'API ---

/**
 * Récupère le calendrier prévu pour un employé.
 */
export const getPlannedCalendar = (employeeId: string, year: number, month: number) => {
  return apiClient.get(`/api/employees/${employeeId}/planned-calendar`, {
    params: { year, month }
  });
};

/** Avertissement renvoyé par POST /planned-calendar (fusion serveur). */
export interface PlannedCalendarWarning {
  jour: number;
  /** ex. "absence_validee_requalifiee" */
  code: string;
  type_avant?: string | null;
  type_apres?: string | null;
  type_refuse?: string | null;
}

export interface UpdatePlannedCalendarResponse {
  status: string;
  message: string;
  /** Absent tant que le backend ne le renvoie pas — traiter comme liste vide. */
  warnings?: PlannedCalendarWarning[];
}

/**
 * Met à jour le calendrier prévu pour un employé.
 */
export const updatePlannedCalendar = (employeeId: string, year: number, month: number, data: PlannedEventData[]) => {
  return apiClient.post<UpdatePlannedCalendarResponse>(`/api/employees/${employeeId}/planned-calendar`, {
    year,
    month,
    calendrier_prevu: data,
  });
};

/**
 * Récupère les heures réelles saisies pour un employé.
 */
export const getActualHours = (employeeId: string, year: number, month: number) => {
  return apiClient.get(`/api/employees/${employeeId}/actual-hours`, {
    params: { year, month }
  });
};

/**
 * Met à jour les heures réelles saisies pour un employé.
 */
export const updateActualHours = (employeeId: string, year: number, month: number, data: ActualHoursData[]) => {
  return apiClient.post(`/api/employees/${employeeId}/actual-hours`, {
    year,
    month,
    calendrier_reel: data,
  });
};

export const calculatePayrollEvents = (employeeId: string, year: number, month: number) => {
  return apiClient.post(`/api/employees/${employeeId}/calculate-payroll-events`, {
    year,
    month,
  });
};

export interface ImportBadgeuseResult {
  status: string;
  employee_id: string;
  year: number;
  month: number;
  days_updated: number;
  days_with_anomaly_warnings: number[];
  warnings: string[];
  payroll_recalculated: boolean;
}

export const importActualHoursFromBadgeuse = (
  employeeId: string,
  year: number,
  month: number,
  options?: { recalculatePayroll?: boolean }
) => {
  return apiClient.post<ImportBadgeuseResult>(
    `/api/employees/${employeeId}/actual-hours/import-badgeuse`,
    {
      year,
      month,
      recalculate_payroll: options?.recalculatePayroll ?? false,
    }
  );
};

export interface ImportBadgeuseBulkResult {
  year: number;
  month: number;
  employees_processed: number;
  total_days_updated: number;
  results: Array<{
    employee_id: string;
    days_updated: number;
    warnings: string[];
    days_with_anomaly_warnings: number[];
    payroll_recalculated: boolean;
  }>;
  errors: Array<{ employee_id: string; message: string }>;
}

export const importBadgeuseActualHoursBulk = (
  companyId: string,
  employeeIds: string[],
  year: number,
  month: number,
  options?: { recalculatePayroll?: boolean }
) => {
  return apiClient.post<ImportBadgeuseBulkResult>(
    '/api/schedules/import-badgeuse-actual-hours',
    {
      company_id: companyId,
      employee_ids: employeeIds,
      year,
      month,
      recalculate_payroll: options?.recalculatePayroll ?? false,
    }
  );
};

// --- SAISIE ASSISTÉE PAR IA (page Calendriers RH) ---

export interface RosterEmployee {
  id: string;
  first_name: string;
  last_name: string;
  time_tracking_id?: string | null;
}

export type DayNature = 'prevu' | 'reel';

export interface AiDayEntry {
  jour: number;
  heures: number | null;
  type: string;
  nature: DayNature;
  punch_entry_raw?: string | null;
  punch_exit_raw?: string | null;
  shift_code?: string | null;
  // Mois/année réels du jour si différents du (year, month) de la proposition
  // (semaine hebdomadaire à cheval sur deux mois). Absent = mois de la proposition.
  year?: number | null;
  month?: number | null;
}

export type AiMatchConfidence = 'high' | 'medium' | 'none';
export type ReviewStatus = 'ok' | 'warning' | 'error' | 'empty';
export type MatchMethod = 'matricule' | 'name_exact' | 'name_fuzzy' | 'none';
export type QualityLevel = 'ok' | 'warning' | 'error' | 'info';

export interface TimesheetQualityCheck {
  level: QualityLevel;
  code: string;
  message: string;
  employee_raw_name?: string | null;
  matricule?: string | null;
}

export interface AffectedMonth {
  year: number;
  month: number;
  days: number[];
}

export interface AiEmployeeProposal {
  raw_name: string;
  employee_id: string | null;
  matched_name: string | null;
  match_confidence: AiMatchConfidence;
  match_method?: MatchMethod;
  time_tracking_id?: string | null;
  review_status?: ReviewStatus;
  days: AiDayEntry[];
  warnings: string[];
  weekly_total_pdf?: number | null;
  weekly_total_imported?: number | null;
  weekly_total_gap?: number | null;
  days_expected_count?: number | null;
  days_imported_count?: number | null;
  coverage_ratio?: number | null;
  quality_issue?: string | null;
}

export type TimesheetScope = 'weekly' | 'monthly' | 'unknown';
export type TimesheetConfidence = 'high' | 'medium' | 'low';
export type DocumentScopeInput = 'auto' | 'weekly' | 'monthly';

export interface AiCalendarProposal {
  year: number;
  month: number;
  source: string;
  employees: AiEmployeeProposal[];
  warnings: string[];
  detected_scope?: TimesheetScope;
  detected_period_start?: string | null;
  detected_period_end?: string | null;
  period_confidence?: TimesheetConfidence;
  period_warnings?: string[];
  detected_days_count?: number;
  suggested_year?: number | null;
  suggested_month?: number | null;
  month_auto_corrected?: boolean;
  requested_year?: number | null;
  requested_month?: number | null;
  month_correction_message?: string | null;
  quality_checks?: TimesheetQualityCheck[];
  detected_format?: string | null;
  parse_confidence?: number | null;
  focus_week_index?: number | null;
  affected_months?: AffectedMonth[];
  roster_not_in_document_count?: number;
  review_summary?: {
    ready: number;
    warning: number;
    error: number;
    empty: number;
    incomplete?: number;
    gap?: number;
    total: number;
  } | null;
  extraction_method?: string | null;
  extraction_warnings?: string[];
  extraction_pages_total?: number | null;
  extraction_pages_processed?: number | null;
  extraction_truncated?: boolean;
  extraction_mode?: string | null;
  consensus_conflicts?: number | null;
}

export type TimesheetExtractJobStatus =
  | 'queued'
  | 'extracting'
  | 'completed'
  | 'failed'
  | 'cancelled';

export interface TimesheetExtractProgress {
  phase: string;
  pages_total: number;
  pages_done: number;
  current_page: number;
  batch_id?: string;
  files_total?: number;
  files_done?: number;
}

export interface TimesheetExtractStartResponse {
  job_id: string;
  status: 'queued' | 'extracting';
}

export interface TimesheetExtractJobResponse {
  job_id: string;
  status: TimesheetExtractJobStatus;
  progress: TimesheetExtractProgress;
  proposal?: AiCalendarProposal | null;
  error_message?: string | null;
  extraction_warnings?: string[];
}

export interface PersistTimesheetEmployeePayload {
  employee_id: string;
  days: AiDayEntry[];
}

/**
 * Avertissement d'écriture d'un import de pointages : jour du relevé refusé
 * parce qu'une absence validée occupe déjà le planning
 * (code "absence_validee_preservee").
 */
export interface TimesheetCommitWarning {
  employee_id?: string | null;
  jour: number;
  code: string;
  message?: string | null;
  type_avant?: string | null;
  type_refuse?: string | null;
}

export interface PersistTimesheetResponse {
  year: number;
  month: number;
  employees_processed: number;
  total_days_written: number;
  results: Array<{
    employee_id: string;
    days_written: number;
    success: boolean;
    error?: string | null;
  }>;
  errors: Array<{ employee_id: string; message: string }>;
  /** Absent tant que le backend ne le renvoie pas — traiter comme liste vide. */
  warnings?: TimesheetCommitWarning[];
}

export interface ExtractTimesheetOptions {
  singleEmployee?: boolean;
  documentScope?: DocumentScopeInput;
  weekAnchorDate?: string | null;
  onProgress?: (progress: TimesheetExtractProgress) => void;
  signal?: AbortSignal;
}

/** État courant de la revue, envoyé pour une correction en delta. */
export interface ParseCurrentProposal {
  employees: {
    name: string;
    days: { jour: number; heures: number | null; type: string; nature: DayNature }[];
  }[];
}

/**
 * Analyse une instruction en langage naturel (texte ou dictée transcrite)
 * et renvoie une proposition d'heures réelles (non persistée).
 *
 * Avec `currentProposal`, la consigne est appliquée comme une correction de
 * la proposition affichée (le backend saute ses raccourcis de régénération).
 */
export const parseScheduleInstruction = async (
  year: number,
  month: number,
  instruction: string,
  employees: RosterEmployee[],
  singleEmployee = false,
  broadcast = false,
  currentProposal?: ParseCurrentProposal,
): Promise<AiCalendarProposal> => {
  const { data } = await apiClient.post<AiCalendarProposal>(
    '/api/schedules/assisted-fill/parse-text',
    {
      year,
      month,
      instruction,
      employees,
      single_employee: singleEmployee,
      broadcast,
      ...(currentProposal ? { current_proposal: currentProposal } : {}),
    },
  );
  return data;
};

/**
 * Lance l'extraction hybride IA en arrière-plan (vision + OCR par page).
 */
export const startTimesheetExtract = async (
  file: File,
  year: number,
  month: number,
  employees: RosterEmployee[],
  options: ExtractTimesheetOptions = {},
): Promise<TimesheetExtractStartResponse> => {
  const {
    singleEmployee = false,
    documentScope = 'auto',
    weekAnchorDate = null,
  } = options;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('year', String(year));
  formData.append('month', String(month));
  formData.append('employees', JSON.stringify(employees));
  formData.append('single_employee', String(singleEmployee));
  formData.append('document_scope', documentScope);
  if (weekAnchorDate) {
    formData.append('week_anchor_date', weekAnchorDate);
  }
  const { data } = await apiClient.post<TimesheetExtractStartResponse>(
    '/api/schedules/assisted-fill/extract-timesheet/start',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
};

export const getTimesheetExtractJob = async (
  jobId: string,
): Promise<TimesheetExtractJobResponse> => {
  const { data } = await apiClient.get<TimesheetExtractJobResponse>(
    `/api/schedules/assisted-fill/extract-timesheet/jobs/${jobId}`,
  );
  return data;
};

export const cancelTimesheetExtractJob = async (
  jobId: string,
): Promise<{ status: string; job_id: string }> => {
  const { data } = await apiClient.delete<{ status: string; job_id: string }>(
    `/api/schedules/assisted-fill/extract-timesheet/jobs/${jobId}`,
  );
  return data;
};

const POLL_INTERVAL_MS = 2000;
const POLL_MAX_ATTEMPTS = 300;

export interface WaitForTimesheetExtractOptions {
  signal?: AbortSignal;
}

/**
 * Attend la fin d'un job d'extraction (polling ~2 s).
 */
export const waitForTimesheetExtractJob = async (
  jobId: string,
  onProgress?: (progress: TimesheetExtractProgress) => void,
  options: WaitForTimesheetExtractOptions = {},
): Promise<AiCalendarProposal> => {
  const { signal } = options;
  for (let attempt = 0; attempt < POLL_MAX_ATTEMPTS; attempt += 1) {
    if (signal?.aborted) {
      throw new DOMException("Import annulé.", "AbortError");
    }
    const job = await getTimesheetExtractJob(jobId);
    onProgress?.(job.progress);
    if (job.status === 'completed' && job.proposal) {
      return job.proposal;
    }
    if (job.status === 'failed') {
      throw new Error(job.error_message ?? "L'analyse du relevé a échoué.");
    }
    if (job.status === 'cancelled') {
      throw new Error("L'import a été annulé.");
    }
    await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
  }
  throw new Error("Délai d'attente dépassé (extraction trop longue).");
};

/**
 * Analyse un relevé de pointeuse (PDF / image) et renvoie une proposition
 * d'heures réelles (non persistée) — chemin async hybride IA.
 */
export const extractTimesheet = async (
  file: File,
  year: number,
  month: number,
  employees: RosterEmployee[],
  options: ExtractTimesheetOptions = {},
): Promise<AiCalendarProposal> => {
  const started = await startTimesheetExtract(file, year, month, employees, options);
  return waitForTimesheetExtractJob(started.job_id, options.onProgress, {
    signal: options.signal,
  });
};

/** @deprecated Sync endpoint — préférer extractTimesheet (async). */
export const extractTimesheetSync = async (
  file: File,
  year: number,
  month: number,
  employees: RosterEmployee[],
  options: ExtractTimesheetOptions = {},
): Promise<AiCalendarProposal> => {
  const {
    singleEmployee = false,
    documentScope = 'auto',
    weekAnchorDate = null,
  } = options;
  const formData = new FormData();
  formData.append('file', file);
  formData.append('year', String(year));
  formData.append('month', String(month));
  formData.append('employees', JSON.stringify(employees));
  formData.append('single_employee', String(singleEmployee));
  formData.append('document_scope', documentScope);
  if (weekAnchorDate) {
    formData.append('week_anchor_date', weekAnchorDate);
  }
  const { data } = await apiClient.post<AiCalendarProposal>(
    '/api/schedules/assisted-fill/extract-timesheet',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
};

export const persistTimesheetBatch = async (
  year: number,
  month: number,
  employees: PersistTimesheetEmployeePayload[],
  options?: { batchId?: string; allowPartial?: boolean; recalculatePayroll?: boolean },
): Promise<PersistTimesheetResponse> => {
  const { data } = await apiClient.post<PersistTimesheetResponse>(
    '/api/schedules/assisted-fill/persist-timesheet',
    {
      year,
      month,
      employees,
      batch_id: options?.batchId ?? null,
      allow_partial: options?.allowPartial ?? false,
      recalculate_payroll: options?.recalculatePayroll ?? false,
    },
  );
  return data;
};

export interface ColumnDetectionResult {
  headers: string[];
  sample_rows: Record<string, string | null>[];
  suggested_mapping: Record<string, string>;
  mapping_complete: boolean;
  source_type: string;
}

export const detectTimesheetColumns = async (file: File): Promise<ColumnDetectionResult> => {
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await apiClient.post<ColumnDetectionResult>(
    '/api/schedules/timesheet-import/detect-columns',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
};

export interface TimesheetImportParseResult {
  batch_id: string;
  status: string;
  preview: AiCalendarProposal;
  parser_key?: string | null;
  file_hash?: string | null;
}

export const parseStructuredTimesheet = async (
  file: File,
  year: number,
  month: number,
  employees: RosterEmployee[],
  columnMapping?: Record<string, string>,
): Promise<TimesheetImportParseResult> => {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('year', String(year));
  formData.append('month', String(month));
  formData.append('employees', JSON.stringify(employees));
  formData.append('column_mapping', JSON.stringify(columnMapping ?? {}));
  const { data } = await apiClient.post<TimesheetImportParseResult>(
    '/api/schedules/timesheet-import/parse',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
};

export type TimesheetImportBatchStatus =
  | 'parsed'
  | 'previewed'
  | 'committing'
  | 'committed'
  | 'failed'
  | 'cancelled';

export interface TimesheetImportBatchSummary {
  committed_days?: number;
  employees_processed?: number;
  /**
   * Jours refusés au commit (absence validée préservée…). Champ défensif :
   * absent tant que le schéma de réponse backend ne l'expose pas.
   */
  commit_warnings?: TimesheetCommitWarning[];
}

export interface TimesheetImportBatchResponse {
  batch_id: string;
  status: TimesheetImportBatchStatus;
  preview?: AiCalendarProposal | null;
  summary?: TimesheetImportBatchSummary | null;
  parser_key?: string | null;
  error_message?: string | null;
}

export const getTimesheetImportBatch = async (
  batchId: string,
): Promise<TimesheetImportBatchResponse> => {
  const { data } = await apiClient.get<TimesheetImportBatchResponse>(
    `/api/schedules/timesheet-import/batches/${batchId}`,
  );
  return data;
};

const BATCH_POLL_MS = 1500;
const BATCH_POLL_MAX = 120;

export const waitForTimesheetImportBatchCommitted = async (
  batchId: string,
): Promise<TimesheetImportBatchResponse> => {
  for (let i = 0; i < BATCH_POLL_MAX; i += 1) {
    const batch = await getTimesheetImportBatch(batchId);
    if (batch.status === 'committed') return batch;
    if (batch.status === 'failed') {
      throw new Error(batch.error_message ?? "L'enregistrement a échoué.");
    }
    await new Promise((r) => setTimeout(r, BATCH_POLL_MS));
  }
  throw new Error("Délai d'attente dépassé (commit import).");
};

export const startTimesheetExtractBatch = async (
  files: File[],
  year: number,
  month: number,
  employees: RosterEmployee[],
  options: ExtractTimesheetOptions = {},
): Promise<{ job_id: string; file_count: number }> => {
  const formData = new FormData();
  files.forEach((f) => formData.append('files', f));
  formData.append('year', String(year));
  formData.append('month', String(month));
  formData.append('employees', JSON.stringify(employees));
  formData.append('single_employee', String(options.singleEmployee ?? false));
  formData.append('document_scope', options.documentScope ?? 'auto');
  const { data } = await apiClient.post<{ job_id: string; file_count: number }>(
    '/api/schedules/timesheet-import/extract-timesheet/start-batch',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
};

export interface TimesheetImportProfile {
  id?: string;
  profile_name: string;
  source_type: string;
  parser_key: string;
  column_mapping: Record<string, string>;
  options: Record<string, unknown>;
}

export const getTimesheetImportProfiles = () =>
  apiClient.get<TimesheetImportProfile[]>('/api/schedules/timesheet-import/profiles');

export const saveTimesheetImportProfile = (profile: Omit<TimesheetImportProfile, 'id'>) =>
  apiClient.put<TimesheetImportProfile>('/api/schedules/timesheet-import/profiles', profile);