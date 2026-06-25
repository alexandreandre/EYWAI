import apiClient from '@/api/apiClient';

export type RibMatchConfidence = 'high' | 'medium' | 'none';
export type RibReviewStatus = 'ok' | 'warning' | 'error';
export type RibMatchMethod =
  | 'nir'
  | 'matricule'
  | 'name_exact'
  | 'name_fuzzy'
  | 'email'
  | 'patronymic'
  | 'patronymic_matricule'
  | 'none';

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
  duplicate_employee_conflict?: boolean;
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
    duplicate_conflicts?: number;
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

export async function parseCpImportFiles(
  files: File[],
  companyId?: string,
): Promise<CpImportParseResponse> {
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
      params: companyId ? { company_id: companyId } : undefined,
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

export type PayrollExportMatchMethod = RibMatchMethod | 'nir';
export type PayrollExportReviewStatus = RibReviewStatus;

export type PayrollExportRowPreview = {
  row_index: number;
  raw_identity: string;
  nir?: string | null;
  email?: string | null;
  employee_id?: string | null;
  matched_name?: string | null;
  match_confidence: RibMatchConfidence;
  match_method: PayrollExportMatchMethod;
  review_status: PayrollExportReviewStatus;
  warnings: string[];
  preview_columns: Record<string, unknown>;
  employee_patch: Record<string, unknown>;
  boeth?: Record<string, unknown> | null;
  team_name?: string | null;
  current_email?: string | null;
  raw_row: Record<string, string>;
};

export type PayrollExportPreviewField = {
  key: string;
  label: string;
  source_header?: string | null;
};

export type PayrollExportParseResponse = {
  company_id: string;
  company_name: string;
  headers: string[];
  column_mapping: Record<string, string>;
  preview_fields?: PayrollExportPreviewField[];
  rows: PayrollExportRowPreview[];
  roster: RibImportRosterEmployee[];
  summary: {
    total: number;
    ready: number;
    warning: number;
    error: number;
    unmatched?: number;
    rib_rows?: number;
    rib_valid_rows?: number;
  };
};

export type PayrollExportCommitRow = {
  row_index: number;
  employee_id: string;
  employee_patch: Record<string, unknown>;
  team_name?: string | null;
  boeth?: Record<string, unknown> | null;
  confirmed: boolean;
};

export type PayrollExportCommitResponse = RibImportCommitResponse;

export async function parsePayrollExportFile(
  companyId: string,
  file: File,
): Promise<PayrollExportParseResponse> {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post<PayrollExportParseResponse>(
    '/api/admin-import/payroll-export/parse',
    form,
    {
      params: { company_id: companyId },
      headers: { 'Content-Type': 'multipart/form-data' },
    },
  );
  return data;
}

export async function commitPayrollExport(payload: {
  company_id: string;
  create_teams_if_missing?: boolean;
  rows: PayrollExportCommitRow[];
}): Promise<PayrollExportCommitResponse> {
  const { data } = await apiClient.post<PayrollExportCommitResponse>(
    '/api/admin-import/payroll-export/commit',
    payload,
  );
  return data;
}

export type CompanySetupNextAction = {
  block: string;
  label: string;
  tab: string;
  priority: number;
};

export type CompanySetupStatus = {
  company_id: string;
  company_name: string;
  idcc?: string | null;
  overall_pct: number;
  blocks: {
    dsn: {
      covered_months: number;
      applicable_months: number;
      applicable_covered_months: number;
      expected_last_period?: string | null;
      gaps?: string[];
      coverage_status?: string;
      complete: boolean;
      last_period?: string | null;
      status: string;
      employees_synced?: boolean;
    };
    employees: {
      total: number;
      profile_complete_pct: number;
      missing_rib_count: number;
    };
    cp: { adjusted_count: number; total_active: number };
    leave_settings: { configured: boolean };
    modulation: { configured: boolean };
    planning: { months_with_calendar: number };
    payroll_params: {
      taux_at_mp?: number | null;
      paie_jour_de_fin?: number | null;
      paie_occurrence?: number | null;
      taux_vm?: number | null;
      taux_fnal?: number | null;
    };
    jei: { configured: boolean };
    oeth: { configured: boolean };
  };
  next_actions: CompanySetupNextAction[];
  payroll_kpi?: {
    ready: boolean;
    source: 'payslip' | 'dsn' | 'none';
    source_label: string;
    period: string;
    gross: number;
    net: number;
    partial: boolean;
  };
};

export async function getCompanySetupStatus(companyId: string): Promise<CompanySetupStatus> {
  const { data } = await apiClient.get<CompanySetupStatus>(
    '/api/admin-import/company-setup-status',
    { params: { company_id: companyId } },
  );
  return data;
}

export async function applyCcnSetupPreset(companyId: string): Promise<{
  company_id: string;
  idcc?: string | null;
  leave_preset_applied: boolean;
  modulation_preset_applied: boolean;
}> {
  const { data } = await apiClient.post(
    '/api/admin-import/ccn-preset/apply',
    null,
    { params: { company_id: companyId } },
  );
  return data;
}

export type PlanningPeriodMode = 'auto' | 'month' | 'year' | 'range';

export type PlanningImportReviewStatus = 'ok' | 'warning' | 'error';

export type PlanningImportReviewItem = {
  raw_name: string;
  employee_id?: string | null;
  matched_name?: string | null;
  review_status: PlanningImportReviewStatus;
  needs_manual_match?: boolean;
  suggested_employee_ids?: string[];
  sommaire_hint?: string | null;
  message: string;
};

export type PlanningImportSummary = {
  validation_status: PlanningImportReviewStatus;
  ready_to_commit: boolean;
  format_label: string;
  period_label: string;
  months_count: number;
  days_total: number;
  sheets_parsed?: number | null;
  employees_total: number;
  employees_ok: number;
  employees_warning: number;
  employees_error: number;
  employees_importable: number;
  assigned_employee_ids: string[];
  unmatched_sheets: string[];
  review_items: PlanningImportReviewItem[];
  review_items_truncated: number;
  warnings: string[];
  commit_hint: string;
};

export type PlanningImportCommitProgress = {
  done: number;
  total: number;
  percent: number;
  phase?: string;
  phase_label?: string;
  label?: string;
  employee_id?: string | null;
  completed_labels?: string[];
  employees_queue?: string[];
};

export type PlanningImportBatchStatus = {
  batch_id: string;
  status: string;
  summary?: Record<string, unknown>;
  commit_progress?: PlanningImportCommitProgress | null;
  employees_processed?: number | null;
  total_days_written?: number | null;
  errors?: Array<{ employee_id?: string; message?: string }>;
  error_message?: string | null;
};

export type PlanningImportRosterEmployee = {
  id: string;
  first_name: string;
  last_name: string;
  time_tracking_id?: string | null;
};

export type PlanningImportParseResponse = {
  company_id: string;
  company_name: string;
  year: number;
  month: number;
  period_mode?: PlanningPeriodMode;
  batch_id: string;
  status: string;
  preview?: Record<string, unknown> | null;
  summary?: PlanningImportSummary | null;
  roster?: PlanningImportRosterEmployee[];
  parser_key?: string | null;
  file_hash?: string | null;
};

export type PlanningImportPeriodParams = {
  periodMode: PlanningPeriodMode;
  year: number;
  month?: number;
  startYear?: number;
  startMonth?: number;
  endYear?: number;
  endMonth?: number;
};

export async function parsePlanningImport(
  companyId: string,
  period: PlanningImportPeriodParams,
  file: File,
): Promise<PlanningImportParseResponse> {
  const form = new FormData();
  form.append('file', file);
  const params: Record<string, string | number> = {
    company_id: companyId,
    year: period.year,
    period_mode: period.periodMode,
  };
  if (period.periodMode === 'month' && period.month != null) {
    params.month = period.month;
  }
  if (period.periodMode === 'range') {
    params.start_year = period.startYear ?? period.year;
    params.start_month = period.startMonth ?? 1;
    params.end_year = period.endYear ?? period.year;
    params.end_month = period.endMonth ?? 12;
  }
  if (period.periodMode === 'auto' && period.month != null) {
    params.month = period.month;
  }
  const { data } = await apiClient.post<PlanningImportParseResponse>(
    '/api/admin-import/planning/parse',
    form,
    {
      params,
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300_000,
    },
  );
  return data;
}

export async function applyPlanningImportMappings(
  batchId: string,
  companyId: string,
  mappings: Array<{ raw_name: string; employee_id: string }>,
): Promise<{ batch_id: string; summary: PlanningImportSummary }> {
  const { data } = await apiClient.post<{ batch_id: string; summary: PlanningImportSummary }>(
    '/api/admin-import/planning/apply-mappings',
    {
      batch_id: batchId,
      company_id: companyId,
      mappings,
    },
  );
  return data;
}

export async function commitPlanningImport(batchId: string, companyId: string): Promise<{
  batch_id: string;
  status: string;
}> {
  const { data } = await apiClient.post<{ batch_id: string; status: string }>(
    '/api/admin-import/planning/commit',
    null,
    { params: { batch_id: batchId, company_id: companyId } },
  );
  return data;
}

export async function getPlanningImportBatch(
  batchId: string,
  companyId: string,
): Promise<PlanningImportBatchStatus> {
  const { data } = await apiClient.get<PlanningImportBatchStatus>(
    `/api/admin-import/planning/batches/${batchId}`,
    { params: { company_id: companyId } },
  );
  return data;
}
