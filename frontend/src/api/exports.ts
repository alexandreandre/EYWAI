// frontend/src/api/exports.ts
// API pour les exports

import apiClient from './apiClient';

export type ExportType = 
  | "journal_paie"
  | "charges_sociales"
  | "conges_absences"
  | "notes_frais"
  | "ecritures_comptables"
  | "od_salaires"
  | "od_charges_sociales"
  | "od_pas"
  | "od_globale"
  | "export_cabinet_generique"
  | "export_cabinet_quadra"
  | "export_cabinet_sage"
  | "dsn_mensuelle"
  | "virement_salaires"
  | "recapitulatif_montants";

export type ExportStatus = "previewed" | "generated" | "cancelled" | "replaced";

export interface ExportPreviewRequest {
  export_type: ExportType;
  period: string; // Format: YYYY-MM
  company_id?: string;
  employee_ids?: string[];
  filters?: Record<string, any>;
  excluded_employee_ids?: string[]; // Pour exclure manuellement des collaborateurs
  execution_date?: string; // Date d'exécution souhaitée
  payment_label?: string; // Libellé de virement
}

export interface ExportAnomaly {
  type: "error" | "warning";
  message: string;
  severity: "blocking" | "warning";
  employee_id?: string;
  employee_name?: string;
}

export interface ExportTotals {
  employees_count: number;
  total_brut?: number;
  total_cotisations_salariales?: number;
  total_cotisations_patronales?: number;
  total_net_imposable?: number;
  total_net_a_payer?: number;
  total_amount?: number;
}

export interface ExportPreviewResponse {
  export_type: ExportType;
  period: string;
  employees_count: number;
  totals: ExportTotals;
  anomalies: ExportAnomaly[];
  warnings: string[];
  can_generate: boolean;
}

export interface ExportGenerateRequest {
  export_type: ExportType;
  period: string;
  company_id?: string;
  employee_ids?: string[];
  filters?: Record<string, any>;
  format: "csv" | "xlsx";
  excluded_employee_ids?: string[]; // Pour exclure manuellement des collaborateurs
  execution_date?: string; // Date d'exécution souhaitée
  payment_label?: string; // Libellé de virement
}

export interface ExportFileInfo {
  filename: string;
  path: string;
  size: number;
  format: "csv" | "xlsx" | "zip" | "xml";
}

export interface ExportReport {
  export_type: ExportType;
  period: string;
  generated_at: string;
  generated_by: string;
  employees_count: number;
  totals: ExportTotals;
  anomalies: ExportAnomaly[];
  warnings: string[];
  parameters: Record<string, any>;
}

export interface ExportGenerateResponse {
  export_id: string;
  export_type: ExportType;
  period: string;
  status: ExportStatus;
  files: ExportFileInfo[];
  report: ExportReport;
  download_urls: Record<string, string>;
}

export interface ExportHistoryEntry {
  id: string;
  export_type: ExportType;
  period: string;
  status: ExportStatus;
  generated_at: string;
  generated_by: string;
  generated_by_name?: string;
  files_count: number;
  totals?: ExportTotals;
}

export interface ExportHistoryResponse {
  exports: ExportHistoryEntry[];
  total: number;
}

// Prévisualiser un export
export async function previewExport(
  request: ExportPreviewRequest
): Promise<ExportPreviewResponse> {
  const response = await apiClient.post('/api/exports/preview', request);
  return response.data;
}

// Générer un export
export async function generateExport(
  request: ExportGenerateRequest
): Promise<ExportGenerateResponse> {
  const response = await apiClient.post('/api/exports/generate', request);
  return response.data;
}

// Récupérer l'historique des exports
export async function getExportHistory(
  exportType?: ExportType,
  period?: string
): Promise<ExportHistoryResponse> {
  const params = new URLSearchParams();
  if (exportType) params.append('export_type', exportType);
  if (period) params.append('period', period);
  
  const response = await apiClient.get(`/api/exports/history?${params.toString()}`);
  return response.data;
}

// Télécharger un export depuis l'historique
export async function downloadExport(exportId: string): Promise<{ download_url: string }> {
  const response = await apiClient.get(`/api/exports/download/${exportId}`);
  return response.data;
}

/** Types alignés sur EXPORT_TYPES_GENERATE (backend) — exports planifiés */
export const SCHEDULABLE_EXPORT_TYPES: ExportType[] = [
  "journal_paie",
  "virement_salaires",
  "od_salaires",
  "od_charges_sociales",
  "od_pas",
  "od_globale",
  "export_cabinet_generique",
  "export_cabinet_quadra",
  "export_cabinet_sage",
  "dsn_mensuelle",
];

export const SCHEDULED_EXPORT_TYPE_LABELS: Partial<Record<ExportType, string>> = {
  journal_paie: "Journal de paie",
  virement_salaires: "Paiement des salaires (virement)",
  od_salaires: "Écritures OD — Salaires",
  od_charges_sociales: "Écritures OD — Charges sociales",
  od_pas: "Écritures OD — PAS",
  od_globale: "Écritures OD — Globale",
  export_cabinet_generique: "Export cabinet (générique)",
  export_cabinet_quadra: "Export cabinet Quadra",
  export_cabinet_sage: "Export cabinet Sage",
  dsn_mensuelle: "DSN mensuelle",
};

export type ScheduledExportFrequency = "daily" | "weekly" | "monthly";

export interface ScheduledExport {
  id: string;
  company_id: string;
  name: string;
  export_type: string;
  export_type_label: string;
  frequency: ScheduledExportFrequency;
  frequency_label: string;
  day_of_week: number | null;
  day_of_month: number | null;
  hour_utc: number;
  recipients: string[];
  is_active: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
}

export interface ScheduledExportCreate {
  name: string;
  export_type: string;
  frequency: ScheduledExportFrequency;
  day_of_week?: number;
  day_of_month?: number;
  hour_utc?: number;
  recipients?: string[];
}

export type ScheduledExportUpdate = Partial<
  Pick<
    ScheduledExportCreate,
    "name" | "export_type" | "frequency" | "day_of_week" | "day_of_month" | "hour_utc" | "recipients"
  >
> & { is_active?: boolean };

function scheduledHeaders(companyId?: string | null): Record<string, string> | undefined {
  if (!companyId) return undefined;
  return { "X-Active-Company": companyId };
}

export async function getScheduledExports(
  companyId: string | null | undefined,
): Promise<ScheduledExport[]> {
  const { data } = await apiClient.get<ScheduledExport[]>("/api/exports/scheduled", {
    headers: scheduledHeaders(companyId),
  });
  return data;
}

export async function createScheduledExport(
  companyId: string | null | undefined,
  body: ScheduledExportCreate,
): Promise<ScheduledExport> {
  const { data } = await apiClient.post<ScheduledExport>(
    "/api/exports/scheduled",
    body,
    { headers: scheduledHeaders(companyId) },
  );
  return data;
}

export async function updateScheduledExport(
  scheduleId: string,
  companyId: string | null | undefined,
  body: ScheduledExportUpdate,
): Promise<ScheduledExport> {
  const { data } = await apiClient.patch<ScheduledExport>(
    `/api/exports/scheduled/${scheduleId}`,
    body,
    { headers: scheduledHeaders(companyId) },
  );
  return data;
}

export async function deleteScheduledExport(
  scheduleId: string,
  companyId: string | null | undefined,
): Promise<void> {
  await apiClient.delete(`/api/exports/scheduled/${scheduleId}`, {
    headers: scheduledHeaders(companyId),
  });
}

export async function runScheduledExportNow(
  scheduleId: string,
  companyId: string | null | undefined,
): Promise<{ export_id: string; message: string }> {
  const { data } = await apiClient.post<{ export_id: string; message: string }>(
    `/api/exports/scheduled/${scheduleId}/run-now`,
    {},
    { headers: scheduledHeaders(companyId) },
  );
  return data;
}

export async function getScheduledExportHistory(
  scheduleId: string,
  companyId: string | null | undefined,
): Promise<ExportHistoryResponse> {
  const { data } = await apiClient.get<ExportHistoryResponse>(
    `/api/exports/scheduled/${scheduleId}/history`,
    { headers: scheduledHeaders(companyId) },
  );
  return data;
}

// --- Envois compta / banque (dispatch) ---

export type DispatchChannel = "compta" | "banque";
export type DispatchStatus = "pending" | "generated" | "transmitted" | "failed";

export interface DispatchChannelStatus {
  channel: DispatchChannel;
  period: string;
  status: DispatchStatus;
  dispatch_id: string | null;
  export_ids: string[];
  files_count: number;
  totals?: ExportTotals;
  generated_at: string | null;
  transmitted_at: string | null;
  transmission_note: string | null;
  can_generate: boolean;
  blocking_anomalies_count: number;
}

export interface DispatchStatusResponse {
  period: string;
  compta: DispatchChannelStatus;
  banque: DispatchChannelStatus;
}

export interface DispatchFileDownload {
  export_id: string;
  export_type: string;
  filename: string;
  download_url: string;
}

export interface DispatchResultResponse {
  dispatch_id: string;
  channel: DispatchChannel;
  period: string;
  status: DispatchStatus;
  export_ids: string[];
  files: ExportFileInfo[];
  downloads: DispatchFileDownload[];
  message: string;
}

export interface DispatchHistoryEntry {
  id: string;
  channel: DispatchChannel;
  period: string;
  status: DispatchStatus;
  export_ids: string[];
  generated_at: string;
  transmitted_at: string | null;
  transmission_note: string | null;
  created_by_name: string | null;
}

export interface DispatchHistoryListResponse {
  dispatches: DispatchHistoryEntry[];
  total: number;
}

export interface DispatchSchedule {
  channel: DispatchChannel;
  schedule_id: string | null;
  name: string;
  export_type: string;
  is_active: boolean;
  day_of_month: number;
  hour_utc: number;
  recipients: string[];
  last_run_at: string | null;
  next_run_at: string | null;
}

export interface DispatchScheduleUpsert {
  is_active: boolean;
  day_of_month: number;
  hour_utc: number;
  recipients?: string[];
}

export const DISPATCH_STATUS_LABELS: Record<DispatchStatus, string> = {
  pending: "À faire",
  generated: "Fichiers générés",
  transmitted: "Transmis",
  failed: "Échec",
};

function dispatchHeaders(companyId?: string | null): Record<string, string> | undefined {
  return scheduledHeaders(companyId);
}

export async function getDispatchStatus(
  companyId: string | null | undefined,
  period: string,
): Promise<DispatchStatusResponse> {
  const { data } = await apiClient.get<DispatchStatusResponse>(
    `/api/exports/dispatch/status?period=${encodeURIComponent(period)}`,
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}

export async function dispatchCompta(
  companyId: string | null | undefined,
  period: string,
  format: "csv" | "xlsx" = "csv",
): Promise<DispatchResultResponse> {
  const { data } = await apiClient.post<DispatchResultResponse>(
    "/api/exports/dispatch/compta",
    { period, format },
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}

export async function dispatchBanque(
  companyId: string | null | undefined,
  body: {
    period: string;
    format?: "csv" | "xlsx";
    execution_date?: string;
    payment_label?: string;
  },
): Promise<DispatchResultResponse> {
  const { data } = await apiClient.post<DispatchResultResponse>(
    "/api/exports/dispatch/banque",
    body,
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}

export async function markDispatchTransmitted(
  companyId: string | null | undefined,
  dispatchId: string,
  note?: string,
): Promise<{ dispatch_id: string; status: DispatchStatus; transmitted_at: string; message: string }> {
  const { data } = await apiClient.post(
    `/api/exports/dispatch/${dispatchId}/mark-transmitted`,
    { note },
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}

export async function getDispatchHistory(
  companyId: string | null | undefined,
  channel?: DispatchChannel,
  limit = 10,
): Promise<DispatchHistoryListResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (channel) params.append("channel", channel);
  const { data } = await apiClient.get<DispatchHistoryListResponse>(
    `/api/exports/dispatch/history?${params.toString()}`,
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}

export async function getDispatchSchedules(
  companyId: string | null | undefined,
): Promise<{ schedules: DispatchSchedule[] }> {
  const { data } = await apiClient.get<{ schedules: DispatchSchedule[] }>(
    "/api/exports/dispatch/schedules",
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}

export async function upsertDispatchSchedule(
  companyId: string | null | undefined,
  channel: DispatchChannel,
  body: DispatchScheduleUpsert,
): Promise<DispatchSchedule> {
  const { data } = await apiClient.put<DispatchSchedule>(
    `/api/exports/dispatch/schedules/${channel}`,
    body,
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}

export async function runDispatchScheduleNow(
  companyId: string | null | undefined,
  channel: DispatchChannel,
  period?: string,
): Promise<{ dispatch_id: string | null; export_id: string | null; message: string }> {
  const params = period ? `?period=${encodeURIComponent(period)}` : "";
  const { data } = await apiClient.post(
    `/api/exports/dispatch/schedules/${channel}/run-now${params}`,
    {},
    { headers: dispatchHeaders(companyId) },
  );
  return data;
}
