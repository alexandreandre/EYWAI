/**
 * API client — fractionnement CP
 */

import apiClient from './apiClient';

export interface FractionnementSettings {
  company_id: string;
  fractionnement_enabled: boolean;
  cp_unit: 'ouvres' | 'ouvrables';
  ouvres_to_ouvrables_ratio: number;
  fifth_week_deduction_ouvres: number;
  calculation_method: 'mbc' | 'manual' | 'legal';
  exclude_forfait_jours: boolean;
}

export type FractionnementSettingsUpdate = Partial<
  Omit<FractionnementSettings, 'company_id'>
>;

export interface FractionnementPreviewRow {
  employee_id: string;
  first_name: string;
  last_name: string;
  grant_year: number;
  solde_cp_n1_ouvres: number;
  cp_reported_june_ouvres: number;
  cp_seniority_deduction_ouvres: number;
  auto_report_june_ouvres?: number;
  auto_seniority_deduction_ouvres?: number;
  report_june_manual_override?: boolean;
  seniority_manual_override?: boolean;
  prefill_source?: Record<string, string>;
  manual_solde_ouvrables?: number;
  solde_ouvres: number;
  solde_ouvrables: number;
  days_granted: number;
  calculation_method?: string;
  status?: string;
}

export interface LeaveCampaignDashboard {
  grant_year: number;
  phase: string;
  today: string;
  cp_seniority: {
    enabled: boolean;
    preset: string;
    employee_count: number;
    total_days: number;
    validated_count: number;
    overridden_count: number;
    warnings_count: number;
    deadline: string;
  };
  fractionnement: {
    enabled: boolean;
    calculation_method: string;
    employee_count: number;
    total_days: number;
    validated_count: number;
    deadline: string;
  };
  alerts: Array<{ level: string; code: string; message: string }>;
}

export async function getFractionnementSettings(): Promise<FractionnementSettings> {
  const res = await apiClient.get<FractionnementSettings>(
    '/api/absences/fractionnement/settings',
  );
  return res.data;
}

export async function updateFractionnementSettings(
  payload: FractionnementSettingsUpdate,
): Promise<FractionnementSettings> {
  const res = await apiClient.put<FractionnementSettings>(
    '/api/absences/fractionnement/settings',
    payload,
  );
  return res.data;
}

export async function getFractionnementPreview(
  grantYear: number,
): Promise<FractionnementPreviewRow[]> {
  const res = await apiClient.get<FractionnementPreviewRow[]>(
    `/api/absences/fractionnement/preview?grant_year=${grantYear}`,
  );
  return res.data;
}

export async function updateFractionnementInput(
  employeeId: string,
  payload: {
    grant_year: number;
    cp_reported_june_ouvres: number;
    cp_seniority_deduction_ouvres?: number;
    report_june_manual_override?: boolean;
    seniority_manual_override?: boolean;
    manual_solde_ouvrables?: number;
  },
): Promise<unknown> {
  const res = await apiClient.put(
    `/api/absences/fractionnement/inputs/${employeeId}`,
    payload,
  );
  return res.data;
}

export async function resetFractionnementInputAuto(
  employeeId: string,
  grantYear: number,
): Promise<unknown> {
  const res = await apiClient.post(
    `/api/absences/fractionnement/inputs/${employeeId}/reset-auto?grant_year=${grantYear}`,
  );
  return res.data;
}

export async function validateFractionnementGrants(
  grantYear: number,
): Promise<{ grant_year: number; validated_count: number; status: string }> {
  const res = await apiClient.post(
    `/api/absences/fractionnement/validate?grant_year=${grantYear}`,
  );
  return res.data;
}

export async function getLeaveCampaignDashboard(
  grantYear?: number,
): Promise<LeaveCampaignDashboard> {
  const q = grantYear ? `?grant_year=${grantYear}` : '';
  const res = await apiClient.get<LeaveCampaignDashboard>(
    `/api/absences/leave-campaign/dashboard${q}`,
  );
  return res.data;
}
