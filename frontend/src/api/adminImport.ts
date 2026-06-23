import apiClient from '@/api/apiClient';

export type RibMatchConfidence = 'high' | 'medium' | 'none';
export type RibReviewStatus = 'ok' | 'warning' | 'error';
export type RibMatchMethod = 'matricule' | 'name_exact' | 'name_fuzzy' | 'email' | 'none';

export type RibImportRowPreview = {
  row_index: number;
  raw_identity: string;
  matricule?: string | null;
  email?: string | null;
  rib_raw: string;
  iban: string;
  bic: string;
  iban_valid: boolean;
  employee_id?: string | null;
  matched_name?: string | null;
  match_confidence: RibMatchConfidence;
  match_method: RibMatchMethod;
  review_status: RibReviewStatus;
  warnings: string[];
  current_iban_masked?: string | null;
  raw_row: Record<string, string>;
};

export type RibImportRosterEmployee = {
  id: string;
  first_name: string;
  last_name: string;
  time_tracking_id?: string | null;
};

export type RibImportParseResponse = {
  company_id: string;
  company_name: string;
  headers: string[];
  column_mapping: Record<string, string>;
  rows: RibImportRowPreview[];
  roster: RibImportRosterEmployee[];
  summary: {
    total: number;
    ready: number;
    warning: number;
    error: number;
  };
};

export type RibImportCommitRow = {
  row_index: number;
  employee_id: string;
  iban: string;
  bic?: string | null;
  confirmed: boolean;
};

export type RibImportCommitResponse = {
  applied: number;
  skipped: number;
  results: Array<{
    row_index: number;
    employee_id: string;
    success: boolean;
    message: string;
    duplicate_warnings: string[];
  }>;
  errors: string[];
};

export async function parseRibImportFile(
  companyId: string,
  file: File,
): Promise<RibImportParseResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<RibImportParseResponse>(
    '/api/admin-import/rib/parse',
    form,
    {
      params: { company_id: companyId },
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
  return data;
}

export async function commitRibImport(payload: {
  company_id: string;
  rows: RibImportCommitRow[];
}): Promise<RibImportCommitResponse> {
  const { data } = await apiClient.post<RibImportCommitResponse>(
    '/api/admin-import/rib/commit',
    payload,
  );
  return data;
}

export type CpMatchConfidence = RibMatchConfidence;
export type CpReviewStatus = RibReviewStatus;
export type CpMatchMethod = RibMatchMethod;

export type CpImportRowPreview = {
  row_index: number;
  source_file: string;
  page_index: number;
  company_id?: string | null;
  company_name?: string | null;
  siret?: string | null;
  period_label?: string | null;
  year: number;
  month?: number | null;
  raw_identity: string;
  matricule?: string | null;
  cp_n1_solde: number;
  cp_n_solde: number;
  acquis_n1?: number | null;
  acquis_n?: number | null;
  pris_n1?: number | null;
  pris_n?: number | null;
  employee_id?: string | null;
  matched_name?: string | null;
  match_confidence: CpMatchConfidence;
  match_method: CpMatchMethod;
  review_status: CpReviewStatus;
  warnings: string[];
  parse_format: string;
  current_cp_n1?: number | null;
  current_cp_n?: number | null;
  delta_cp_n1?: number | null;
  delta_cp_n?: number | null;
  has_existing_adjustment: boolean;
};

export type CpImportRosterEmployee = RibImportRosterEmployee;

export type CpImportParseResponse = {
  rows: CpImportRowPreview[];
  rosters_by_company: Record<string, CpImportRosterEmployee[]>;
  summary: {
    total: number;
    ready: number;
    warning: number;
    error: number;
    files_processed: number;
    files_failed: number;
    duplicates_removed: number;
  };
  file_errors: string[];
};

export type CpImportCommitRow = {
  row_index: number;
  company_id: string;
  employee_id: string;
  year: number;
  month?: number | null;
  cp_n1_solde: number;
  cp_n_solde: number;
  source_file?: string | null;
  period_label?: string | null;
  confirmed: boolean;
};

export type CpImportCommitResponse = {
  applied: number;
  skipped: number;
  results: Array<{
    row_index: number;
    employee_id: string;
    success: boolean;
    message: string;
    duplicate_warnings: string[];
  }>;
  errors: string[];
};

const CP_MAX_FILES = 1000;

export async function parseCpImportFiles(files: File[]): Promise<CpImportParseResponse> {
  if (files.length === 0) {
    throw new Error('Aucun fichier sélectionné.');
  }
  if (files.length > CP_MAX_FILES) {
    throw new Error(`Maximum ${CP_MAX_FILES} fichiers par import.`);
  }
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  const { data } = await apiClient.post<CpImportParseResponse>(
    '/api/admin-import/cp/parse',
    form,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300_000,
    },
  );
  return data;
}

export async function commitCpImport(payload: {
  rows: CpImportCommitRow[];
}): Promise<CpImportCommitResponse> {
  const { data } = await apiClient.post<CpImportCommitResponse>(
    '/api/admin-import/cp/commit',
    payload,
  );
  return data;
}
