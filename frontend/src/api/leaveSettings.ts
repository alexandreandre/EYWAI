import apiClient from '@/api/apiClient';

export type CpCountingUnit = 'ouvrable' | 'ouvre';

export interface LeaveSettings {
  company_id: string;
  cp_acquisition_days_per_month: number;
  cp_counting_unit: CpCountingUnit;
  cp_reference_period_start_month: number;
  cp_carryover_enabled: boolean;
  cp_carryover_max_days: number | null;
  cp_acquisition_rate_display: number;
  cp_annual_days_display: number;
  rtt_annual_days: number | null;
  rtt_use_calendar_formula: boolean;
  rtt_use_forfait_jours_formula: boolean;
  rtt_forfait_annual_days: number;
  rtt_forfait_cp_ouvres_deduction: number;
  rtt_forfait_cadres_only?: boolean;
  rtt_annual_days_computed: number;
  rtt_period_start_month: number;
  rtt_period_end_month: number;
  rtt_carryover_enabled: boolean;
  rtt_year_end_reminder_enabled: boolean;
  rtt_year_end_reminder_days_before: number;
  configured: boolean;
}

export type LeaveSettingsUpdate = Partial<
  Pick<
    LeaveSettings,
    | 'cp_acquisition_days_per_month'
    | 'cp_counting_unit'
    | 'cp_reference_period_start_month'
    | 'cp_carryover_enabled'
    | 'cp_carryover_max_days'
    | 'rtt_annual_days'
    | 'rtt_use_calendar_formula'
    | 'rtt_use_forfait_jours_formula'
    | 'rtt_forfait_annual_days'
    | 'rtt_forfait_cp_ouvres_deduction'
    | 'rtt_forfait_cadres_only'
    | 'rtt_period_start_month'
    | 'rtt_period_end_month'
    | 'rtt_carryover_enabled'
    | 'rtt_year_end_reminder_enabled'
    | 'rtt_year_end_reminder_days_before'
  >
>;

export interface EmployeeLeaveAdjustment {
  employee_id: string;
  year: number;
  cp_n1_opening_balance: number;
  cp_n_opening_balance: number;
  rtt_opening_balance: number;
  rtt_forfeited_at: string | null;
  rtt_forfeited_days: number;
  note: string | null;
}

export type EmployeeLeaveAdjustmentUpdate = Partial<
  Pick<
    EmployeeLeaveAdjustment,
    'cp_n1_opening_balance' | 'cp_n_opening_balance' | 'rtt_opening_balance' | 'note'
  >
>;

export interface EmployeeRttSoldeUpdate {
  rtt_solde: number;
  note?: string | null;
}

export interface LeaveBalanceOverviewItem {
  employee_id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  cp_n1_remaining: number;
  cp_n_remaining: number;
  cp_total_remaining: number;
  cp_legal_days?: number;
  cp_seniority_days?: number;
  fractionnement_days?: number;
  cp_seniority_status?: string | null;
  rtt_remaining: number;
  rtt_opening_balance?: number;
  adjustment_note: string | null;
}

export interface LeaveBalancesOverview {
  year: number;
  employees: LeaveBalanceOverviewItem[];
}

export interface RttYearEndOverviewItem {
  employee_id: string;
  first_name: string;
  last_name: string;
  rtt_remaining: number;
  already_closed: boolean;
  closure_required: boolean;
}

export interface RttYearEndOverview {
  year: number;
  reminder_active: boolean;
  employees: RttYearEndOverviewItem[];
}

export type LeaveNotificationRole = 'admin' | 'rh' | 'collaborateur_rh';

export interface LeaveNotificationSettings {
  company_id: string;
  enabled: boolean;
  notify_on_employee_request: boolean;
  notify_after_manager_approval: boolean;
  recipient_roles: LeaveNotificationRole[];
  extra_recipient_emails: string[];
  configured: boolean;
}

export type LeaveNotificationSettingsUpdate = Partial<
  Pick<
    LeaveNotificationSettings,
    | 'enabled'
    | 'notify_on_employee_request'
    | 'notify_after_manager_approval'
    | 'recipient_roles'
    | 'extra_recipient_emails'
  >
>;

export interface LeaveAdjustmentImportRow {
  email?: string;
  matricule?: string;
  first_name?: string;
  last_name?: string;
  cp_n1_solde: number;
  cp_n_solde: number;
  rtt_solde: number;
  year: number;
}

export async function getLeaveSettings(): Promise<LeaveSettings> {
  const { data } = await apiClient.get<LeaveSettings>('/api/absences/leave-settings');
  return data;
}

export async function updateLeaveSettings(
  payload: LeaveSettingsUpdate,
): Promise<LeaveSettings> {
  const { data } = await apiClient.patch<LeaveSettings>(
    '/api/absences/leave-settings',
    payload,
  );
  return data;
}

export async function getLeaveBalancesOverview(
  year?: number,
): Promise<LeaveBalancesOverview> {
  const { data } = await apiClient.get<LeaveBalancesOverview>(
    '/api/absences/leave-settings/balances-overview',
    { params: year ? { year } : undefined },
  );
  return data;
}

export async function getEmployeeLeaveAdjustment(
  employeeId: string,
  year: number,
): Promise<EmployeeLeaveAdjustment> {
  const { data } = await apiClient.get<EmployeeLeaveAdjustment>(
    `/api/absences/leave-settings/employees/${employeeId}/adjustment`,
    { params: { year } },
  );
  return data;
}

export async function updateEmployeeLeaveAdjustment(
  employeeId: string,
  year: number,
  payload: EmployeeLeaveAdjustmentUpdate,
): Promise<EmployeeLeaveAdjustment> {
  const { data } = await apiClient.patch<EmployeeLeaveAdjustment>(
    `/api/absences/leave-settings/employees/${employeeId}/adjustment`,
    payload,
    { params: { year } },
  );
  return data;
}

export async function updateEmployeeRttSolde(
  employeeId: string,
  year: number,
  payload: EmployeeRttSoldeUpdate,
): Promise<EmployeeLeaveAdjustment> {
  const { data } = await apiClient.patch<EmployeeLeaveAdjustment>(
    `/api/absences/leave-settings/employees/${employeeId}/rtt-solde`,
    payload,
    { params: { year } },
  );
  return data;
}

export async function importLeaveAdjustments(
  rows: LeaveAdjustmentImportRow[],
): Promise<{ imported: number; errors: string[] }> {
  const { data } = await apiClient.post<{ imported: number; errors: string[] }>(
    '/api/absences/leave-settings/adjustments/import',
    { rows },
  );
  return data;
}

export async function getRttYearEndOverview(
  year?: number,
): Promise<RttYearEndOverview> {
  const { data } = await apiClient.get<RttYearEndOverview>(
    '/api/absences/rtt-year-end/overview',
    { params: year ? { year } : undefined },
  );
  return data;
}

export async function closeRttYearEnd(
  year: number,
  employeeIds: string[],
): Promise<{ closed_count: number; total_days_forfeited: number }> {
  const { data } = await apiClient.post<{
    closed_count: number;
    total_days_forfeited: number;
  }>('/api/absences/rtt-year-end/close', { year, employee_ids: employeeIds });
  return data;
}

export async function getLeaveNotificationSettings(): Promise<LeaveNotificationSettings> {
  const { data } = await apiClient.get<LeaveNotificationSettings>(
    '/api/absences/leave-notification-settings',
  );
  return data;
}

export async function updateLeaveNotificationSettings(
  payload: LeaveNotificationSettingsUpdate,
): Promise<LeaveNotificationSettings> {
  const { data } = await apiClient.put<LeaveNotificationSettings>(
    '/api/absences/leave-notification-settings',
    payload,
  );
  return data;
}
