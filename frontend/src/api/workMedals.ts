import apiClient from '@/api/apiClient';

export type MedalLevel = 'argent' | 'vermeil' | 'or' | 'grand_or';
export type SeniorityBasis =
  | 'seniority_reference_date'
  | 'total_career'
  | 'company_only';
export type AmountMode = 'fixed' | 'salary_months';
export type WorkMedalCaseStatus =
  | 'upcoming'
  | 'awaiting_employee'
  | 'awaiting_rh'
  | 'approved'
  | 'paid'
  | 'dismissed';

export interface MedalTier {
  level: MedalLevel;
  years: number;
  label: string;
  amount_mode: AmountMode;
  amount_value: number;
}

export interface WorkMedalSettings {
  id?: string | null;
  company_id: string;
  enabled: boolean;
  seniority_basis: SeniorityBasis;
  reminder_months_before: number;
  tiers: MedalTier[];
  default_is_taxable: boolean;
  default_is_socially_taxed: boolean;
  created_at?: string | null;
  updated_at?: string | null;
}

export type WorkMedalSettingsUpdate = Partial<
  Omit<WorkMedalSettings, 'id' | 'company_id' | 'created_at' | 'updated_at'>
>;

export interface WorkMedalCase {
  id: string;
  company_id: string;
  employee_id: string;
  medal_level: MedalLevel;
  milestone_years: number;
  eligible_date: string;
  status: WorkMedalCaseStatus;
  amount_computed?: number | null;
  payroll_year?: number | null;
  payroll_month?: number | null;
  monthly_input_id?: string | null;
  employee_confirmed_at?: string | null;
  rh_validated_at?: string | null;
  rh_validated_by?: string | null;
  dismissed_reason?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
  employee_first_name?: string | null;
  employee_last_name?: string | null;
}

export interface WorkMedalSummary {
  awaiting_rh: number;
  awaiting_employee: number;
  upcoming: number;
  total_actionable: number;
}

export interface WorkMedalScanResult {
  created: number;
  updated: number;
  notifications_sent: number;
}

export const DEFAULT_MEDAL_TIERS: MedalTier[] = [
  {
    level: 'argent',
    years: 20,
    label: 'Médaille d\'argent (20 ans)',
    amount_mode: 'fixed',
    amount_value: 400,
  },
  {
    level: 'vermeil',
    years: 30,
    label: 'Médaille de vermeil (30 ans)',
    amount_mode: 'fixed',
    amount_value: 600,
  },
  {
    level: 'or',
    years: 35,
    label: 'Médaille d\'or (35 ans)',
    amount_mode: 'fixed',
    amount_value: 800,
  },
  {
    level: 'grand_or',
    years: 40,
    label: 'Grande médaille d\'or (40 ans)',
    amount_mode: 'fixed',
    amount_value: 1000,
  },
];

export async function getWorkMedalSettings(): Promise<WorkMedalSettings> {
  const res = await apiClient.get<WorkMedalSettings>('/api/work-medal-settings/');
  return res.data;
}

export async function saveWorkMedalSettings(
  payload: WorkMedalSettingsUpdate,
): Promise<WorkMedalSettings> {
  const res = await apiClient.put<WorkMedalSettings>('/api/work-medal-settings/', payload);
  return res.data;
}

export async function listWorkMedalCases(params?: {
  status?: string;
  medal_level?: string;
}): Promise<WorkMedalCase[]> {
  const res = await apiClient.get<WorkMedalCase[]>('/api/work-medals/', { params });
  return res.data;
}

export async function getWorkMedalSummary(): Promise<WorkMedalSummary> {
  const res = await apiClient.get<WorkMedalSummary>('/api/work-medals/summary');
  return res.data;
}

export async function scanWorkMedals(): Promise<WorkMedalScanResult> {
  const res = await apiClient.post<WorkMedalScanResult>('/api/work-medals/scan');
  return res.data;
}

export async function listEmployeeWorkMedalCases(
  employeeId: string,
): Promise<WorkMedalCase[]> {
  const res = await apiClient.get<WorkMedalCase[]>(`/api/work-medals/employees/${employeeId}`);
  return res.data;
}

export async function approveWorkMedalCase(
  caseId: string,
  payload: { payroll_year: number; payroll_month: number; amount_override?: number },
): Promise<WorkMedalCase> {
  const res = await apiClient.post<WorkMedalCase>(`/api/work-medals/${caseId}/approve`, payload);
  return res.data;
}

export async function dismissWorkMedalCase(
  caseId: string,
  reason?: string,
): Promise<WorkMedalCase> {
  const res = await apiClient.post<WorkMedalCase>(`/api/work-medals/${caseId}/dismiss`, {
    reason,
  });
  return res.data;
}

export const MEDAL_LEVEL_LABELS: Record<MedalLevel, string> = {
  argent: 'Médaille d\'argent',
  vermeil: 'Médaille de vermeil',
  or: 'Médaille d\'or',
  grand_or: 'Grande médaille d\'or',
};

export const CASE_STATUS_LABELS: Record<WorkMedalCaseStatus, string> = {
  upcoming: 'À venir',
  awaiting_employee: 'À valider RH',
  awaiting_rh: 'À valider RH',
  approved: 'Validé',
  paid: 'Payé',
  dismissed: 'Ignoré',
};
