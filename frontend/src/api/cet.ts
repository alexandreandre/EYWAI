/**
 * API client — Compte Épargne Temps (CET)
 */

import apiClient from './apiClient';

export type CetValidationMode = 'auto' | 'rh' | 'manager' | 'manager_then_rh';

export interface CetSettings {
  company_id: string;
  cet_enabled: boolean;
  agreement_reference: string | null;
  hours_per_rest_day: number;
  request_deadline_day_of_month: number | null;
  validation_mode: CetValidationMode;
  allow_deposit_hs: boolean;
  allow_deposit_cp: boolean;
  max_cp_days_per_year: number | null;
  max_account_balance_days: number | null;
  cp_unit: 'ouvres' | 'ouvrables';
  ouvres_to_ouvrables_ratio: number;
  cp_debit_timing: 'on_validation' | 'on_payroll';
  hs_debit_timing: 'on_validation' | 'on_payroll';
}

export type CetSettingsUpdate = Partial<Omit<CetSettings, 'company_id'>>;

export interface CetPendingMovement {
  id: string;
  movement_type: string;
  hours: number;
  days: number;
  status: string;
  workflow_step: string;
  year: number;
  month: number;
  created_at?: string | null;
  note?: string | null;
}

export interface CetMovementDetail extends CetPendingMovement {
  employee_id: string;
  balance_after_days?: number | null;
}

export interface CetPendingManagerItem extends CetMovementDetail {
  employee?: {
    id: string;
    first_name: string;
    last_name: string;
  };
}

export interface CetSummary {
  employee_id: string;
  company_id: string;
  cet_enabled: boolean;
  eligible: boolean;
  has_manager: boolean;
  allow_deposit_hs: boolean;
  allow_deposit_cp: boolean;
  cp_unit: 'ouvres' | 'ouvrables';
  year: number;
  month: number;
  balance_hours: number;
  balance_days: number;
  overtime_hours_month: number;
  spareable_hours: number;
  rest_days_available: number;
  hours_per_rest_day: number;
  cp_transfer_used_days: number;
  cp_transfer_remaining_days: number | null;
  cp_balance_available: number;
  pending_movements: CetPendingMovement[];
  settings: CetSettings;
}

export interface CetOverviewRow {
  employee_id: string;
  first_name: string;
  last_name: string;
  balance_hours: number;
  balance_days: number;
  cp_transfer_used_days: number;
  cp_transfer_remaining_days: number | null;
  pending_count: number;
  has_manager: boolean;
  last_movement_at: string | null;
}

export async function getCetSettings(): Promise<CetSettings> {
  const res = await apiClient.get<CetSettings>('/api/cet/settings');
  return res.data;
}

export async function updateCetSettings(
  payload: CetSettingsUpdate,
): Promise<CetSettings> {
  const res = await apiClient.put<CetSettings>('/api/cet/settings', payload);
  return res.data;
}

export async function getCetOverview(year?: number): Promise<CetOverviewRow[]> {
  const search = year != null ? `?year=${year}` : '';
  const res = await apiClient.get<CetOverviewRow[]>(`/api/cet/overview${search}`);
  return res.data;
}

export async function getCetPending(): Promise<CetMovementDetail[]> {
  const res = await apiClient.get<CetMovementDetail[]>('/api/cet/pending');
  return res.data;
}

export async function getPendingManagerCetApproval(
  companyId?: string,
): Promise<CetPendingManagerItem[]> {
  const qs = companyId ? `?company_id=${encodeURIComponent(companyId)}` : '';
  const res = await apiClient.get<CetPendingManagerItem[]>(
    `/api/cet/pending-manager-approval${qs}`,
  );
  return res.data;
}

export async function getMyCetSummary(params?: {
  year?: number;
  month?: number;
}): Promise<CetSummary> {
  const search = new URLSearchParams();
  if (params?.year != null) search.set('year', String(params.year));
  if (params?.month != null) search.set('month', String(params.month));
  const qs = search.toString();
  const res = await apiClient.get<CetSummary>(
    `/api/cet/me/summary${qs ? `?${qs}` : ''}`,
  );
  return res.data;
}

export async function getMyCetMovements(year?: number): Promise<CetMovementDetail[]> {
  const search = year != null ? `?year=${year}` : '';
  const res = await apiClient.get<CetMovementDetail[]>(
    `/api/cet/me/movements${search}`,
  );
  return res.data;
}

export async function createCetDeposit(payload: {
  hours: number;
  year?: number;
  month?: number;
}): Promise<unknown> {
  const res = await apiClient.post('/api/cet/me/deposits', payload);
  return res.data;
}

export async function createCetDepositCp(payload: {
  days: number;
  year?: number;
  month?: number;
}): Promise<unknown> {
  const res = await apiClient.post('/api/cet/me/deposits/cp', payload);
  return res.data;
}

export async function createCetWithdrawal(payload: {
  hours: number;
}): Promise<unknown> {
  const res = await apiClient.post('/api/cet/me/withdrawals', payload);
  return res.data;
}

export async function getEmployeeCetSummary(
  employeeId: string,
  params?: { year?: number; month?: number; companyId?: string },
): Promise<CetSummary> {
  const search = new URLSearchParams();
  if (params?.year != null) search.set('year', String(params.year));
  if (params?.month != null) search.set('month', String(params.month));
  if (params?.companyId) search.set('company_id', params.companyId);
  const qs = search.toString();
  const res = await apiClient.get<CetSummary>(
    `/api/cet/employees/${employeeId}/summary${qs ? `?${qs}` : ''}`,
  );
  return res.data;
}

export async function getEmployeeCetMovements(
  employeeId: string,
  params?: { year?: number; companyId?: string },
): Promise<CetMovementDetail[]> {
  const search = new URLSearchParams();
  if (params?.year != null) search.set('year', String(params.year));
  if (params?.companyId) search.set('company_id', params.companyId);
  const qs = search.toString();
  const res = await apiClient.get<CetMovementDetail[]>(
    `/api/cet/employees/${employeeId}/movements${qs ? `?${qs}` : ''}`,
  );
  return res.data;
}

export async function validateCetMovement(
  movementId: string,
  approved: boolean,
  companyId?: string,
  rejectionReason?: string,
): Promise<unknown> {
  const search = companyId
    ? `?company_id=${encodeURIComponent(companyId)}`
    : '';
  const res = await apiClient.patch(
    `/api/cet/movements/${movementId}${search}`,
    { approved, rejection_reason: rejectionReason ?? null },
  );
  return res.data;
}

export async function managerApproveCetMovement(
  movementId: string,
  approved: boolean,
  companyId?: string,
  rejectionReason?: string,
): Promise<unknown> {
  const search = companyId
    ? `?company_id=${encodeURIComponent(companyId)}`
    : '';
  const res = await apiClient.post(
    `/api/cet/movements/${movementId}/manager-approve${search}`,
    { approved, rejection_reason: rejectionReason ?? null },
  );
  return res.data;
}

export async function createCetOpeningBalance(payload: {
  employee_id: string;
  hours: number;
  note?: string;
}): Promise<unknown> {
  const res = await apiClient.post('/api/cet/opening-balances', payload);
  return res.data;
}

export async function createCetAdjustment(payload: {
  employee_id: string;
  hours?: number;
  days?: number;
  note: string;
}): Promise<unknown> {
  const res = await apiClient.post('/api/cet/adjustments', payload);
  return res.data;
}

export async function exportCetOverviewCsv(year?: number): Promise<Blob> {
  const rows = await getCetOverview(year);
  const header = [
    'Salarié',
    'Solde (j)',
    'Solde (h)',
    'CP transférés',
    'Quota restant',
    'En attente',
    'Manager',
  ];
  const lines = rows.map((r) => [
    `${r.last_name} ${r.first_name}`.trim(),
    String(r.balance_days),
    String(r.balance_hours),
    String(r.cp_transfer_used_days),
    r.cp_transfer_remaining_days != null
      ? String(r.cp_transfer_remaining_days)
      : '',
    String(r.pending_count),
    r.has_manager ? 'oui' : 'non',
  ]);
  const csv = [header, ...lines]
    .map((line) => line.map((c) => `"${c.replace(/"/g, '""')}"`).join(';'))
    .join('\n');
  return new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
}
