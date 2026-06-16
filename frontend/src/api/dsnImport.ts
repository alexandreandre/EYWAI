import apiClient from './apiClient';

export type DsnImportAnomaly = {
  type: string;
  message: string;
  severity: string;
  source_ref?: string | null;
  meta?: Record<string, unknown>;
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
  is_existing?: boolean | null;
  existing_employee_id?: string | null;
};

export type DsnImportCompany = {
  id: string;
  company_name: string;
  siret?: string | null;
  siren?: string | null;
  group_id?: string | null;
  group_name?: string | null;
  is_active?: boolean;
};

export type DsnImportActionsSummary = {
  totals: { create: number; update: number; skip: number };
  by_type: Record<string, { create: number; update: number; skip: number }>;
};

export type DsnImportRevalidateResponse = {
  anomalies: DsnImportAnomaly[];
  can_commit: boolean;
  summary: Record<string, unknown>;
  items: DsnImportItemPreview[];
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

export type DsnImportMode = 'onboarding' | 'monthly';

export type DsnSyncMode = 'external' | 'native' | 'transition';

export type DsnCoverageStatus =
  | 'ok'
  | 'late'
  | 'missing'
  | 'never'
  | 'not_applicable';

export type DsnCoverageTimelineMonth = {
  period: string;
  month: number;
  state: 'covered' | 'missing' | 'future';
};

export type DsnCoverage = {
  company_id: string;
  dsn_sync_mode: DsnSyncMode;
  status: DsnCoverageStatus;
  expected_last_period: string;
  last_period?: string | null;
  last_import_at?: string | null;
  months_covered: string[];
  gaps: string[];
  timeline: DsnCoverageTimelineMonth[];
  batch_count: number;
  recent_batches: Array<{
    batch_id: string;
    created_at?: string | null;
    period_min?: string | null;
    period_max?: string | null;
    import_mode?: string | null;
    periods: string[];
  }>;
  alerts: Array<{ code: string; severity: string; label: string; [key: string]: unknown }>;
};

export type DsnCoverageAdminSummary = {
  late_count: number;
  companies: Array<{
    company_id: string;
    company_name?: string;
    status: DsnCoverageStatus;
    expected_last_period?: string;
    last_period?: string | null;
    gaps_count?: number;
  }>;
  all_companies?: Array<{
    company_id: string;
    company_name?: string;
    status: DsnCoverageStatus;
    dsn_sync_mode?: DsnSyncMode;
  }>;
};

export type DsnCoverageMatrixCompany = {
  company_id: string;
  company_name?: string | null;
  group_name?: string | null;
  siret?: string | null;
  dsn_sync_mode: DsnSyncMode;
  status: DsnCoverageStatus;
  expected_last_period: string;
  last_period?: string | null;
  last_import_at?: string | null;
  gaps_count: number;
  months_covered: string[];
  timeline: DsnCoverageTimelineMonth[];
};

export type DsnCoverageAdminMatrixResponse = {
  year: number;
  companies: DsnCoverageMatrixCompany[];
};

export type DsnImportLaunchConfig = {
  mode: DsnImportMode;
  targetCompanyId?: string | null;
  resumeBatchId?: string | null;
  suggestedPeriod?: string | null;
};

export type ActivateImportedEmployeeResponse = {
  employee_id: string;
  user_id: string;
  email: string;
  generated_password: string;
};

export async function parseDsnImportFiles(
  files: File[],
  options?: {
    importMode?: DsnImportMode;
    targetCompanyId?: string | null;
    intendedPeriod?: string | null;
  },
): Promise<DsnImportParseResponse> {
  const form = new FormData();
  files.forEach((file) => form.append('files', file));
  const params: Record<string, string> = {};
  if (options?.importMode) params.import_mode = options.importMode;
  if (options?.targetCompanyId) params.target_company_id = options.targetCompanyId;
  if (options?.intendedPeriod) params.intended_period = options.intendedPeriod;
  const { data } = await apiClient.post<DsnImportParseResponse>('/api/dsn-import/parse', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    params,
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

export async function listPendingDsnImportBatches(limit = 20): Promise<DsnImportBatchSummary[]> {
  const { data } = await apiClient.get<{ batches: DsnImportBatchSummary[] }>(
    '/api/dsn-import/batches/pending',
    { params: { limit } },
  );
  return data.batches;
}

export async function fetchDsnCoverage(companyId: string): Promise<DsnCoverage> {
  const { data } = await apiClient.get<DsnCoverage>('/api/dsn-import/coverage', {
    params: { company_id: companyId },
  });
  return data;
}

export async function fetchDsnAdminLateSummary(): Promise<DsnCoverageAdminSummary> {
  const { data } = await apiClient.get<DsnCoverageAdminSummary>(
    '/api/dsn-import/coverage/admin-summary',
  );
  return data;
}

export async function fetchDsnAdminCoverageMatrix(
  year: number,
): Promise<DsnCoverageAdminMatrixResponse> {
  const { data } = await apiClient.get<DsnCoverageAdminMatrixResponse>(
    '/api/dsn-import/coverage/admin-matrix',
    { params: { year } },
  );
  return data;
}

export async function getDsnImportBatch(batchId: string): Promise<DsnImportBatchDetail> {
  const { data } = await apiClient.get<DsnImportBatchDetail>(`/api/dsn-import/batches/${batchId}`);
  return data;
}

export async function commitDsnImportBatch(
  batchId: string,
  overrides: Record<string, string> = {},
  payloadEdits: Record<string, Record<string, unknown>> = {},
  targetCompanyId: string | null = null,
  options?: { importMode?: DsnImportMode | null; replaceExistingPeriods?: boolean },
): Promise<DsnImportCommitStartResponse> {
  const { data } = await apiClient.post<DsnImportCommitStartResponse>(
    `/api/dsn-import/batches/${batchId}/commit`,
    {
      overrides,
      payload_edits: payloadEdits,
      target_company_id: targetCompanyId,
      import_mode: options?.importMode ?? null,
      replace_existing_periods: options?.replaceExistingPeriods ?? false,
    },
  );
  return data;
}

export async function revalidateDsnImportBatch(
  batchId: string,
  payloadEdits: Record<string, Record<string, unknown>> = {},
  targetCompanyId: string | null = null,
): Promise<DsnImportRevalidateResponse> {
  const { data } = await apiClient.post<DsnImportRevalidateResponse>(
    `/api/dsn-import/batches/${batchId}/revalidate`,
    { payload_edits: payloadEdits, target_company_id: targetCompanyId },
  );
  return data;
}

export async function listDsnImportCompanies(): Promise<DsnImportCompany[]> {
  const { data } = await apiClient.get<{ companies: DsnImportCompany[] }>(
    '/api/dsn-import/companies',
  );
  return data.companies;
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
