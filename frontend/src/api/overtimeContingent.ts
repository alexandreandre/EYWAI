/**
 * API client — suivi contingent heures supplémentaires
 */

import apiClient from './apiClient';

export type ContingentStatus =
  | 'ok'
  | 'near_limit'
  | 'management_exceeded'
  | 'cor_exceeded';

export interface ContingentSettings {
  company_id: string;
  legal_cor_contingent_hours: number;
  management_contingent_hours: number | null;
  hours_per_rest_day: number;
  include_structural_hours: boolean;
  pause_deduction_enabled: boolean;
  pause_hs_deduction_per_workday: number;
  workdays_per_year_for_pause: number;
}

export type ContingentSettingsUpdate = Partial<
  Omit<ContingentSettings, 'company_id'>
>;

export interface ContingentKPIs {
  total_employees: number;
  near_limit_count: number;
  management_exceeded_count: number;
  cor_exceeded_count: number;
}

export interface ContingentOverviewRow {
  employee_id: string;
  first_name: string;
  last_name: string;
  hire_date: string | null;
  employment_status?: string | null;
  structural_hours: number;
  paid_hours: number;
  pause_deduction: number;
  manual_adjustment: number;
  rcr_hours: number;
  consumed_hours: number;
  total_for_ceiling: number;
  margin_hours: number;
  legal_cor_excess: number;
  management_contingent: number;
  legal_cor_contingent: number;
  usage_percent: number;
  status: ContingentStatus;
}

export interface ContingentOverview {
  company_id: string;
  year: number;
  reference_date: string;
  settings: ContingentSettings;
  kpis: ContingentKPIs;
  employees: ContingentOverviewRow[];
}

export interface ContingentMonthlyRow {
  month: number;
  paid_hours: number;
  cumulative_consumed: number;
  cumulative_total: number;
}

export interface ContingentEmployeeDetail {
  employee_id: string;
  first_name: string;
  last_name: string;
  hire_date: string | null;
  year: number;
  reference_date: string;
  breakdown: Omit<
    ContingentOverviewRow,
    'employee_id' | 'first_name' | 'last_name' | 'hire_date' | 'employment_status'
  >;
  monthly: ContingentMonthlyRow[];
  adjustment: {
    opening_balance_hours: number;
    note: string | null;
  };
  settings: ContingentSettings;
}

export async function getContingentSettings(): Promise<ContingentSettings> {
  const res = await apiClient.get<ContingentSettings>(
    '/api/repos-compensateur/settings',
  );
  return res.data;
}

export async function updateContingentSettings(
  payload: ContingentSettingsUpdate,
): Promise<ContingentSettings> {
  const res = await apiClient.put<ContingentSettings>(
    '/api/repos-compensateur/settings',
    payload,
  );
  return res.data;
}

export async function getContingentOverview(params: {
  year: number;
  reference_date?: string;
}): Promise<ContingentOverview> {
  const search = new URLSearchParams({ year: String(params.year) });
  if (params.reference_date) {
    search.set('reference_date', params.reference_date);
  }
  const res = await apiClient.get<ContingentOverview>(
    `/api/repos-compensateur/overview?${search.toString()}`,
  );
  return res.data;
}

export async function getContingentEmployeeDetail(
  employeeId: string,
  params: { year: number; reference_date?: string },
): Promise<ContingentEmployeeDetail> {
  const search = new URLSearchParams({ year: String(params.year) });
  if (params.reference_date) {
    search.set('reference_date', params.reference_date);
  }
  const res = await apiClient.get<ContingentEmployeeDetail>(
    `/api/repos-compensateur/employees/${employeeId}?${search.toString()}`,
  );
  return res.data;
}

export async function updateEmployeeContingentAdjustment(
  employeeId: string,
  params: {
    year: number;
    opening_balance_hours: number;
    note?: string | null;
  },
): Promise<{ opening_balance_hours: number; note: string | null }> {
  const search = new URLSearchParams({ year: String(params.year) });
  const res = await apiClient.put(
    `/api/repos-compensateur/employees/${employeeId}/adjustment?${search.toString()}`,
    {
      opening_balance_hours: params.opening_balance_hours,
      note: params.note ?? null,
    },
  );
  return res.data;
}
