import apiClient from '@/api/apiClient';

export interface ModulationSettings {
  company_id: string;
  enabled: boolean;
  configured: boolean;
  reference_period_months: number;
  average_weekly_hours: number;
  weekly_high_hours: number;
  weekly_low_hours: number;
  high_weeks_per_cycle: number;
  low_weeks_per_cycle: number;
  cycle_start_week_iso: string | null;
  pay_smoothed: boolean;
  weekly_cap_hours: number;
  theoretical_annual_hours: number | null;
  hour_account_enabled: boolean;
  hs_franchise_hours_per_period: number | null;
  hs_franchise_period: 'month' | 'pay_period';
  max_account_balance_hours: number | null;
  account_credit_source: 'overtime_only' | 'surplus_over_modulated';
  recovery_absence_enabled: boolean;
  recovery_debit_timing: 'on_validation' | 'on_payroll';
}

export type ModulationSettingsUpdate = Partial<
  Omit<ModulationSettings, 'company_id' | 'configured'>
>;

export interface WeekScheduleTemplate {
  id?: string;
  name: string;
  weekly_hours: number;
  day_configs: Record<string, unknown>[];
  modulation_tier: 'high' | 'low' | 'neutral';
  is_active: boolean;
}

export interface ModulationOverviewRow {
  employee_id: string;
  first_name: string;
  last_name: string;
  theoretical_hours: number;
  actual_hours: number;
  balance_hours: number;
  account_balance_hours: number;
  period_credited_hours: number;
  period_paid_hours: number;
}

export interface ModulationBalance {
  employee_id: string;
  year: number;
  account_balance_hours: number;
  acquired_hours: number;
  taken_hours: number;
  franchise_remaining_hours: number;
}

export interface ModulationMovement {
  id: string;
  employee_id: string;
  year: number;
  month: number | null;
  movement_type: string;
  hours: number;
  status: string;
  source: string;
  reference_id: string | null;
  metadata: Record<string, unknown>;
  note: string | null;
  created_at: string | null;
}

export interface ModulationWorkflowStatus {
  pending_movements: number;
  over_balance_employees: number;
  alert_count: number;
  hour_account_enabled: boolean;
  modulation_enabled: boolean;
}

export async function getModulationSettings(): Promise<ModulationSettings> {
  const { data } = await apiClient.get<ModulationSettings>('/api/modulation/settings');
  return data;
}

export async function updateModulationSettings(
  payload: ModulationSettingsUpdate,
): Promise<ModulationSettings> {
  const { data } = await apiClient.patch<ModulationSettings>(
    '/api/modulation/settings',
    payload,
  );
  return data;
}

export async function listWeekTemplates(): Promise<WeekScheduleTemplate[]> {
  const { data } = await apiClient.get<WeekScheduleTemplate[]>(
    '/api/modulation/week-templates',
  );
  return data;
}

export async function createWeekTemplate(
  payload: WeekScheduleTemplate,
): Promise<WeekScheduleTemplate> {
  const { data } = await apiClient.post<WeekScheduleTemplate>(
    '/api/modulation/week-templates',
    payload,
  );
  return data;
}

export async function deleteWeekTemplate(templateId: string): Promise<void> {
  await apiClient.delete(`/api/modulation/week-templates/${templateId}`);
}

export async function getModulationOverview(
  year?: number,
): Promise<ModulationOverviewRow[]> {
  const { data } = await apiClient.get<ModulationOverviewRow[]>(
    '/api/modulation/overview',
    { params: year ? { year } : undefined },
  );
  return data;
}

export async function getEmployeeModulationBalance(
  employeeId: string,
  year?: number,
  month?: number,
): Promise<ModulationBalance> {
  const { data } = await apiClient.get<ModulationBalance>(
    `/api/modulation/employees/${employeeId}/balance`,
    { params: { year, month } },
  );
  return data;
}

export async function getEmployeeModulationMovements(
  employeeId: string,
  year?: number,
): Promise<ModulationMovement[]> {
  const { data } = await apiClient.get<ModulationMovement[]>(
    `/api/modulation/employees/${employeeId}/movements`,
    { params: year ? { year } : undefined },
  );
  return data;
}

export async function createOpeningBalance(
  employeeId: string,
  hours: number,
  note?: string,
): Promise<ModulationMovement> {
  const { data } = await apiClient.post<ModulationMovement>(
    `/api/modulation/employees/${employeeId}/opening-balance`,
    { hours, note },
  );
  return data;
}

export async function getModulationWorkflowStatus(): Promise<ModulationWorkflowStatus> {
  const { data } = await apiClient.get<ModulationWorkflowStatus>(
    '/api/modulation/workflow-status',
  );
  return data;
}

export async function applyModulationPreset(
  preset: string,
): Promise<ModulationSettings> {
  const { data } = await apiClient.post<ModulationSettings>(
    `/api/modulation/settings/apply-preset/${preset}`,
  );
  return data;
}

export async function createModulationAdjustment(
  employeeId: string,
  hours: number,
  note?: string,
): Promise<ModulationMovement> {
  const { data } = await apiClient.post<ModulationMovement>(
    '/api/modulation/adjustments',
    { employee_id: employeeId, hours, note },
  );
  return data;
}
