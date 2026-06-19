/**
 * API client — CP ancienneté (congés payés supplémentaires)
 */

import apiClient from './apiClient';

export interface CpSeniorityTier {
  category: 'ouvrier_etam' | 'cadre' | 'forfait' | 'all';
  min_years: number;
  days: number;
  min_age?: number | null;
  max_years?: number | null;
}

export interface CpSeniorityRules {
  mode: 'tier_total' | 'cumulative_rules';
  tiers: CpSeniorityTier[];
}

export interface CpSenioritySettings {
  company_id: string;
  enabled: boolean;
  configured: boolean;
  preset: 'plasturgie_idcc_0292' | 'lewis_agreement' | 'metallurgie_idcc_3248' | 'custom';
  seniority_reference: 'cp_period_end';
  seniority_basis: 'company_only' | 'include_prior_service' | 'seniority_reference_date';
  counting_unit: 'ouvrable' | 'ouvre';
  rules: CpSeniorityRules;
  forfait_annual_days_default: number;
  forfait_reduction_enabled: boolean;
  company_agreement_overrides: boolean;
  recommended_preset?: string | null;
  rules_source?: string | null;
}

export type CpSenioritySettingsUpdate = Partial<
  Omit<CpSenioritySettings, 'company_id' | 'configured' | 'recommended_preset' | 'rules_source' | 'rules'>
> & { rules?: CpSeniorityRules };

export interface CpSeniorityPreviewRow {
  employee_id: string;
  first_name: string;
  last_name: string;
  statut?: string | null;
  category?: string | null;
  seniority_years_at_ref: number;
  days_granted: number;
  days_before_prorata?: number;
  prorata_applied?: boolean;
  forfait_days_reduction: number;
  forfait_annual_days_adjusted?: number | null;
  reference_date: string;
  tier_matched?: Record<string, unknown> | null;
  warnings?: string[];
  status?: string;
}

export async function getCpSenioritySettings(): Promise<CpSenioritySettings> {
  const res = await apiClient.get<CpSenioritySettings>(
    '/api/absences/cp-seniority-settings',
  );
  return res.data;
}

export async function updateCpSenioritySettings(
  payload: CpSenioritySettingsUpdate,
): Promise<CpSenioritySettings> {
  const res = await apiClient.patch<CpSenioritySettings>(
    '/api/absences/cp-seniority-settings',
    payload,
  );
  return res.data;
}

export async function applyCpSeniorityPreset(
  preset: string,
): Promise<CpSenioritySettings> {
  const res = await apiClient.post<CpSenioritySettings>(
    `/api/absences/cp-seniority-settings/apply-preset/${preset}`,
  );
  return res.data;
}

export async function getCpSeniorityPreview(
  grantYear: number,
): Promise<CpSeniorityPreviewRow[]> {
  const res = await apiClient.get<CpSeniorityPreviewRow[]>(
    `/api/absences/cp-seniority-settings/preview?grant_year=${grantYear}`,
  );
  return res.data;
}

export async function validateCpSeniorityGrants(
  grantYear: number,
): Promise<{ grant_year: number; validated_count: number; status: string }> {
  const res = await apiClient.post(
    `/api/absences/cp-seniority-settings/validate?grant_year=${grantYear}`,
  );
  return res.data;
}

export async function overrideCpSeniorityGrant(
  employeeId: string,
  payload: { grant_year: number; days_granted: number; note?: string },
): Promise<unknown> {
  const res = await apiClient.patch(
    `/api/absences/cp-seniority-grants/${employeeId}`,
    payload,
  );
  return res.data;
}
