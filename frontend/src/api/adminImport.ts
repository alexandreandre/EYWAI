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
