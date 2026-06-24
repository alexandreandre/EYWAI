import apiClient from './apiClient';

export type WorkforceGap = {
  gap_id: string;
  employee_id: string;
  employee_name: string;
  nir_masked: string;
  gap_type: 'missing_from_dsn' | 'new_hire_not_in_dsn' | 'contract_end_in_dsn';
  hire_date?: string | null;
  period?: string | null;
  likely_scenario?: 'new_hire' | 'departure' | 'unknown' | null;
  suggested_last_working_day?: string | null;
  contract_end_date?: string | null;
  resolution?: WorkforceResolution | null;
};

export type WorkforceReconciliationSummary = {
  enabled: boolean;
  company_id?: string | null;
  period?: string | null;
  gaps: WorkforceGap[];
  unresolved_count: number;
  resolved_count: number;
  active_without_nir_count?: number;
  dsn_employee_count?: number;
  active_db_count?: number;
  excluded_out_of_scope_count?: number;
  gap_counts_by_type?: {
    new_hire_not_in_dsn?: number;
    missing_from_dsn?: number;
    contract_end_in_dsn?: number;
  };
  resolutions?: Record<string, WorkforceResolution>;
};

export type WorkforceResolution = {
  gap_id: string;
  employee_id: string;
  action:
    | 'open_exit'
    | 'close_departure'
    | 'ignore'
    | 'acknowledge_new_hire'
    | 'delete_permanently';
  exit_type?: string | null;
  last_working_day?: string | null;
  exit_reason?: string | null;
  ignore_reason?: string | null;
  hire_date?: string | null;
};

export type WorkforceReconciliationReport = {
  closed: Array<{ gap_id: string; employee_id: string; exit_id?: string }>;
  ignored: Array<{ gap_id: string; employee_id: string; ignore_reason?: string | null }>;
  open_exit_deferred: Array<{
    gap_id: string;
    employee_id: string;
    exit_type?: string;
    last_working_day?: string;
  }>;
  acknowledged_new_hires?: Array<{
    gap_id: string;
    employee_id: string;
    hire_date?: string | null;
  }>;
  deleted?: Array<{ gap_id: string; employee_id: string }>;
  failed?: Array<{ gap_id: string; employee_id: string; error: string }>;
};

export type DsnImportIssue = {
  code: string;
  message: string;
  hint?: string | null;
  severity: string;
  source_ref?: string | null;
  item_label?: string | null;
  meta?: Record<string, unknown>;
};

export type DsnImportAnomaly = DsnImportIssue & {
  type: string;
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
  existing_company_id?: string | null;
  payroll_conflicts?: Record<string, { existing: unknown; dsn: unknown }> | null;
  payroll_extract?: Record<string, unknown> | null;
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

export type DsnImportCommitError = DsnImportIssue;

export type DsnReimportOrphans = {
  count: number;
  employees: Array<{
    employee_id: string;
    employee_name: string;
    nir_masked: string;
  }>;
};

export type DsnImportOrphanRemovalReport = {
  requested_count?: number;
  removed_count?: number;
  removed?: Array<{ employee_id: string; employee_name: string }>;
  failed?: Array<{ employee_id: string; employee_name: string; error: string }>;
};

export type DsnImportCommitResponse = {
  stats: Record<string, number>;
  errors: DsnImportCommitError[];
  error_messages?: string[];
  group_id?: string | null;
  companies: Record<string, string>;
  imported_employees: ImportedEmployeeSummary[];
  workforce_reconciliation?: WorkforceReconciliationReport;
  orphan_removal?: DsnImportOrphanRemovalReport;
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
  next_import_period?: string | null;
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
  at_mp_configured?: boolean;
  payroll_calendar_configured?: boolean;
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
  /** true si clic sur un mois déjà importé (case verte) */
  reimport?: boolean;
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
  options?: {
    importMode?: DsnImportMode | null;
    replaceExistingPeriods?: boolean;
    workforceResolutions?: WorkforceResolution[];
    removeOrphanImportedEmployees?: boolean;
  },
): Promise<DsnImportCommitStartResponse> {
  const { data } = await apiClient.post<DsnImportCommitStartResponse>(
    `/api/dsn-import/batches/${batchId}/commit`,
    {
      overrides,
      payload_edits: payloadEdits,
      target_company_id: targetCompanyId,
      import_mode: options?.importMode ?? null,
      replace_existing_periods: options?.replaceExistingPeriods ?? false,
      workforce_resolutions: options?.workforceResolutions ?? [],
      remove_orphan_imported_employees: options?.removeOrphanImportedEmployees ?? false,
    },
  );
  return data;
}

export async function saveDsnWorkforceResolutions(
  batchId: string,
  resolutions: WorkforceResolution[],
): Promise<{ summary: Record<string, unknown>; workforce_reconciliation: WorkforceReconciliationSummary }> {
  const { data } = await apiClient.patch<{
    summary: Record<string, unknown>;
    workforce_reconciliation: WorkforceReconciliationSummary;
  }>(`/api/dsn-import/batches/${batchId}/workforce-resolutions`, {
    resolutions,
  });
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

export type DsnImportRevokePeriodResponse = {
  company_id: string;
  period: string;
  cumuls_deleted: number;
};

export async function revokeDsnPeriodImport(
  companyId: string,
  period: string,
): Promise<DsnImportRevokePeriodResponse> {
  const { data } = await apiClient.post<DsnImportRevokePeriodResponse>(
    '/api/dsn-import/coverage/revoke-period',
    { company_id: companyId, period },
  );
  return data;
}

export const DSN_IMPORT_REVIEW_REASON_LABELS: Record<string, string> = {
  brut_absent: 'Brut non extrait de la DSN',
  nir_incomplet: 'NIR absent (NTT ou matricule utilisé)',
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
