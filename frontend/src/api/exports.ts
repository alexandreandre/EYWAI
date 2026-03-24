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

