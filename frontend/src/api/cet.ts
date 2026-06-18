/**
 * API client — Compte Épargne Temps (CET)
 */

import apiClient from './apiClient';

export interface CetSettings {
  company_id: string;
  cet_enabled: boolean;
  agreement_reference: string | null;
  hours_per_rest_day: number;
  request_deadline_day_of_month: number | null;
  validation_mode: 'auto' | 'rh';
  allow_deposit_hs: boolean;
  allow_deposit_cp: boolean;
  max_cp_days_per_year: number | null;
  max_account_balance_days: number | null;
  cp_unit: 'ouvres' | 'ouvrables';
  ouvres_to_ouvrables_ratio: number;
  cp_debit_timing: 'on_validation' | 'on_payroll';
  hs_debit_timing: 'on_validation' | 'on_payroll';
}

export type CetSettingsUpdate = Partial<
  Omit<CetSettings, 'company_id'>
>;

export interface CetPendingMovement {
  id: string;
  movement_type: string;
  hours: number;
  days: number;
  status: string;
  year: number;
  month: number;
  created_at?: string | null;
}

export interface CetSummary {
  employee_id: string;
  company_id: string;
  cet_enabled: boolean;
  eligible: boolean;
  allow_deposit_hs: boolean;
  allow_deposit_cp: boolean;
  cp_unit: 'ouvres' | 'ouvrables';
  year: number;
  month: number;
  balance_hours: number;
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

export async function validateCetMovement(
  movementId: string,
  approved: boolean,
  companyId?: string,
): Promise<unknown> {
  const search = companyId
    ? `?company_id=${encodeURIComponent(companyId)}`
    : '';
  const res = await apiClient.patch(
    `/api/cet/movements/${movementId}${search}`,
    { approved },
  );
  return res.data;
}
