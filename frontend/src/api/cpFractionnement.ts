/**
 * API client — fractionnement CP (formule MBC)
 */

import apiClient from './apiClient';

export interface FractionnementSettings {
  company_id: string;
  fractionnement_enabled: boolean;
  cp_unit: 'ouvres' | 'ouvrables';
  ouvres_to_ouvrables_ratio: number;
  fifth_week_deduction_ouvres: number;
}

export type FractionnementSettingsUpdate = Partial<
  Omit<FractionnementSettings, 'company_id'>
>;

export interface FractionnementPreviewRow {
  employee_id: string;
  first_name: string;
  last_name: string;
  solde_cp_n1_ouvres: number;
  cp_reported_june_ouvres: number;
  cp_seniority_deduction_ouvres: number;
  solde_ouvres: number;
  solde_ouvrables: number;
  days_granted: number;
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
  },
): Promise<unknown> {
  const res = await apiClient.put(
    `/api/absences/fractionnement/inputs/${employeeId}`,
    payload,
  );
  return res.data;
}
