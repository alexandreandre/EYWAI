import apiClient from './apiClient';

export type IjssLineStatus = 'pending' | 'partial' | 'ok' | 'variance' | 'justified';

export interface IjssPeriod {
  id: string;
  company_id: string;
  period_year: number;
  period_month: number;
  status: string;
  expected_total: number;
  received_cpam_total: number;
  received_bank_total: number;
  variance_total: number;
}

export interface IjssDashboardRow {
  expected_line_id?: string | null;
  employee_id: string;
  employee_name: string;
  absence_request_id?: string | null;
  ijss_theorique: number;
  ijss_subrogees_bulletin: number;
  received_cpam: number;
  received_bank: number;
  line_status: IjssLineStatus;
  subrogation_active: boolean;
  ijss_brut_validated?: number | null;
  validation_source?: string | null;
  applied_to_payslip_at?: string | null;
  applied_ijss_brut?: number | null;
}

export interface IjssPeriodDashboard {
  period: IjssPeriod;
  summary: { ok: number; variance: number; pending: number };
  rows: IjssDashboardRow[];
  unmatched_received?: IjssUnmatchedReceivedLine[];
}

export interface IjssUnmatchedReceivedLine {
  id: string;
  source: string;
  amount: number;
  employee_name_raw?: string | null;
  employee_nir?: string | null;
  payment_date?: string | null;
}

export interface IjssAbsenceStatus {
  status: string;
  absence_request_id: string;
  expected_line_id?: string | null;
  ijss_subrogees_bulletin?: number;
  ijss_brut_validated?: number | null;
  applied_to_payslip_at?: string | null;
  applied_ijss_brut?: number | null;
}

export const IJSS_ABSENCE_STATUS_LABELS: Record<string, string> = {
  pending: 'IJSS en attente CPAM',
  ok: 'IJSS rapprochée',
  justified: 'IJSS justifiée',
  variance: 'IJSS — écart',
  partial: 'IJSS partiel',
};

export async function getIjssPeriodDashboard(
  year: number,
  month: number,
): Promise<IjssPeriodDashboard> {
  const { data } = await apiClient.get<IjssPeriodDashboard>('/api/ijss-tracking/periods', {
    params: { year, month },
  });
  return data;
}

export async function syncIjssExpected(periodId: string): Promise<{ synced_count: number }> {
  const { data } = await apiClient.post(`/api/ijss-tracking/periods/${periodId}/sync-expected`);
  return data;
}

export async function closeIjssPeriod(periodId: string, notes?: string): Promise<unknown> {
  const { data } = await apiClient.post(`/api/ijss-tracking/periods/${periodId}/close`, {
    notes: notes ?? null,
  });
  return data;
}

export async function syncCpamDecomptes(periodId: string): Promise<{
  success: boolean;
  message: string;
  fallback?: string;
}> {
  const { data } = await apiClient.post(`/api/ijss-tracking/periods/${periodId}/sync-cpam`);
  return data;
}

export async function importBankRecap(periodId: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post(
    `/api/ijss-tracking/periods/${periodId}/import/bank`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function importCpamDecompte(periodId: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  const { data } = await apiClient.post(
    `/api/ijss-tracking/periods/${periodId}/import/cpam`,
    form,
    { headers: { 'Content-Type': 'multipart/form-data' } },
  );
  return data;
}

export async function commitIjssImportBatch(batchId: string) {
  const { data } = await apiClient.post(`/api/ijss-tracking/import/batches/${batchId}/commit`);
  return data;
}

export async function justifyIjssVariance(
  expectedLineId: string,
  content: string,
): Promise<unknown> {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/expected-lines/${expectedLineId}/justify`,
    { content },
  );
  return data;
}

export async function validateIjssExpectedLine(
  expectedLineId: string,
  amount?: number,
  source?: 'cpam_decompte' | 'bank_transfer' | 'manual',
) {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/expected-lines/${expectedLineId}/validate`,
    { amount: amount ?? null, source: source ?? null },
  );
  return data;
}

export async function applyIjssToPayslip(expectedLineId: string) {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/expected-lines/${expectedLineId}/apply-to-payslip`,
  );
  return data;
}

export async function applyAllValidatedIjss(periodId: string) {
  const { data } = await apiClient.post(
    `/api/ijss-tracking/periods/${periodId}/apply-validated`,
  );
  return data;
}

export async function getAbsenceIjssStatus(absenceId: string): Promise<IjssAbsenceStatus> {
  const { data } = await apiClient.get<IjssAbsenceStatus>(
    `/api/ijss-tracking/absences/${absenceId}/ijss`,
  );
  return data;
}

export async function matchIjssReceivedLine(
  lineId: string,
  employeeId: string,
  expectedLineId?: string,
) {
  const { data } = await apiClient.patch(
    `/api/ijss-tracking/received-lines/${lineId}/match`,
    {
      employee_id: employeeId,
      expected_line_id: expectedLineId ?? null,
    },
  );
  return data;
}

export async function downloadIjssAuditExport(periodId: string): Promise<Blob> {
  const { data } = await apiClient.get(`/api/ijss-tracking/periods/${periodId}/export-audit`, {
    responseType: 'blob',
  });
  return data;
}

export const IJSS_LINE_STATUS_LABELS: Record<IjssLineStatus, string> = {
  ok: 'OK',
  partial: 'Partiel',
  variance: 'Écart',
  justified: 'Justifié',
  pending: 'En attente',
};

export interface IjssImportProfile {
  id?: string;
  batch_type: string;
  profile_name: string;
  column_mapping: Record<string, unknown>;
}

export async function getIjssImportProfiles(): Promise<IjssImportProfile[]> {
  const { data } = await apiClient.get<IjssImportProfile[]>(
    '/api/ijss-tracking/import-profiles',
  );
  return data;
}

export async function updateIjssImportProfile(
  batchType: 'bank_recap' | 'cpam_decompte_file',
  columnMapping: Record<string, unknown>,
): Promise<IjssImportProfile> {
  const { data } = await apiClient.put<IjssImportProfile>(
    `/api/ijss-tracking/import-profiles/${batchType}`,
    { column_mapping: columnMapping },
  );
  return data;
}
