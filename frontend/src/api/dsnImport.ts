import apiClient from './apiClient';

export type DsnImportAnomaly = {
  type: string;
  message: string;
  severity: string;
  source_ref?: string | null;
};

export type DsnImportItemPreview = {
  item_type: string;
  source_ref: string;
  action: string;
  mapped_payload: Record<string, unknown>;
  label?: string | null;
  needs_review?: boolean | null;
  review_reasons?: string[] | null;
  preview_columns?: Record<string, unknown> | null;
  employee_count?: number | null;
  editable_fields?: Record<string, string> | null;
  is_scaffold?: boolean | null;
};

export type DsnImportActionsSummary = {
  totals: { create: number; update: number; skip: number };
  by_type: Record<string, { create: number; update: number; skip: number }>;
};

export type DsnImportRevalidateResponse = {
  anomalies: DsnImportAnomaly[];
  can_commit: boolean;
  summary: Record<string, unknown>;
};

export type DsnImportParseResponse = {
  batch_id: string;
  summary: Record<string, unknown>;
  anomalies: DsnImportAnomaly[];
  items: DsnImportItemPreview[];
  can_commit: boolean;
};

export type DsnImportBatchSummary = {
  id: string;
  uploaded_by: string;
  file_names: string[];
  siren?: string | null;
  period_min?: string | null;
  period_max?: string | null;
  status: string;
  summary: Record<string, unknown>;
  created_at?: string | null;
  updated_at?: string | null;
};

export type DsnImportBatchDetail = {
  batch: DsnImportBatchSummary;
  items: Record<string, unknown>[];
  preview: Record<string, unknown>;
  summary: Record<string, unknown>;
};

export type ImportedEmployeeSummary = {
  employee_id: string;
  company_id: string;
  full_name: string;
  placeholder_email?: string | null;
  employment_status?: string | null;
};

export type DsnImportCommitResponse = {
  stats: Record<string, number>;
  errors: string[];
  group_id?: string | null;
  companies: Record<string, string>;
  imported_employees: ImportedEmployeeSummary[];
};

export type DsnImportCommitStartResponse = {
  status: string;
  batch_id: string;
};

export type DsnImportBatchStatus =
  | 'parsed'
  | 'previewed'
  | 'committing'
  | 'committed'
  | 'failed';

export type ActivateImportedEmployeeResponse = {
  employee_id: string;
  user_id: string;
  email: string;
  generated_password: string;
};

export async function parseDsnImportFiles(files: File[]): Promise<DsnImportParseResponse> {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  const { data } = await apiClient.post<DsnImportParseResponse>('/api/dsn-import/parse', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return data;
}

export async function listDsnImportBatches(limit = 50): Promise<DsnImportBatchSummary[]> {
  const { data } = await apiClient.get<{ batches: DsnImportBatchSummary[] }>(
    '/api/dsn-import/batches',
    { params: { limit } },
  );
  return data.batches;
}

export async function getDsnImportBatch(batchId: string): Promise<DsnImportBatchDetail> {
  const { data } = await apiClient.get<DsnImportBatchDetail>(`/api/dsn-import/batches/${batchId}`);
  return data;
}

export async function commitDsnImportBatch(
  batchId: string,
  overrides: Record<string, string> = {},
  payloadEdits: Record<string, Record<string, unknown>> = {},
): Promise<DsnImportCommitStartResponse> {
  const { data } = await apiClient.post<DsnImportCommitStartResponse>(
    `/api/dsn-import/batches/${batchId}/commit`,
    { overrides, payload_edits: payloadEdits },
  );
  return data;
}

export async function revalidateDsnImportBatch(
  batchId: string,
  payloadEdits: Record<string, Record<string, unknown>> = {},
): Promise<DsnImportRevalidateResponse> {
  const { data } = await apiClient.post<DsnImportRevalidateResponse>(
    `/api/dsn-import/batches/${batchId}/revalidate`,
    { payload_edits: payloadEdits },
  );
  return data;
}

export async function activateImportedEmployee(
  employeeId: string,
  companyId: string,
  email: string,
): Promise<ActivateImportedEmployeeResponse> {
  const { data } = await apiClient.post<ActivateImportedEmployeeResponse>(
    '/api/dsn-import/employees/activate',
    { employee_id: employeeId, company_id: companyId, email },
  );
  return data;
}

export const DSN_IMPORT_REVIEW_REASON_LABELS: Record<string, string> = {
  brut_absent: 'Brut absent',
  identifiant_absent: 'NIR / matricule absent',
};

export const DSN_IMPORT_ACTION_LABELS: Record<string, string> = {
  create: 'Créer',
  update: 'Mettre à jour',
  skip: 'Ignorer',
};

export const DSN_IMPORT_ITEM_TYPE_LABELS: Record<string, string> = {
  group: 'Conteneur groupe (SIREN)',
  establishment: 'Entreprise (SIRET)',
  employee: 'Salarié',
  cumul: 'Cumuls',
  collective_agreement: 'Convention collective',
};
