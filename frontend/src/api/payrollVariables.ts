import apiClient from '@/api/apiClient';

export type PayrollVariableRuleType =
  | 'fixed_monthly'
  | 'per_astreinte_week'
  | 'per_shift_type'
  | 'per_modulation_payout'
  | 'per_night_hour'
  | 'per_astreinte_weekend_km'
  | 'per_astreinte_week_tiered'
  | 'per_astreinte_weekend_majoration'
  | 'per_week_without_absence';

export interface PresenceWeekRuleConditions {
  amount_per_week?: number;
  absence_types?: string[];
  workflow_steps?: string[];
  min_locked_shifts_per_week?: number;
  export_code?: string;
}

export type AstreinteKmQuantityMode =
  | 'once_if_eligible'
  | 'per_qualifying_week'
  | 'per_weekend_work_day'
  | 'per_manual_trips';

export type AstreinteKmLinkMode = 'month_overlap' | 'same_iso_week';

export type AstreinteKmRateMode = 'coefficient_a' | 'full_bareme';

export interface AstreinteKmRuleConditions {
  km_free_threshold_one_way?: number;
  round_trip_multiplier?: number;
  requires_astreinte?: boolean;
  requires_weekend_work?: boolean;
  astreinte_link_mode?: AstreinteKmLinkMode;
  quantity_mode?: AstreinteKmQuantityMode;
  rate_mode?: AstreinteKmRateMode;
  vehicle_type_default?: string;
  manual_trips_input_name?: string;
  bareme_segment_index?: number;
}

export interface AstreinteWeekTieredConditions {
  amount_normal?: number;
  amount_christmas?: number;
  amount_bridge?: number;
  christmas_mode?: 'replace' | 'add';
  bridge_mode?: 'add' | 'replace';
  christmas_detection?: 'iso_dec_25' | 'special_day_tag';
  bridge_requires_astreinte_on_day?: boolean;
}

export interface AstreinteWeekendMajorationConditions {
  weekday_rates?: Record<string, number>;
  min_hours?: number;
  flat_hours?: number;
  requires_astreinte_same_iso_week?: boolean;
  weekend_weekday_numbers?: number[];
}

export interface PayrollVariablePreviewDetails {
  eligible?: boolean;
  skip_reason?: string;
  distance_km_one_way?: number;
  km_eligible?: number;
  rate?: number;
  quantity_mode?: string;
  quantity?: number;
  unit_amount?: number;
  vehicle_cv?: number;
  vehicle_type?: string;
  christmas?: boolean;
  monday?: string;
  bridge_dates?: string[];
  heures_faites?: number;
  majoration_rate?: number;
  work_date?: string;
}

export interface PayrollVariableRule {
  id?: string;
  code: string;
  label: string;
  enabled: boolean;
  rule_type: PayrollVariableRuleType;
  bonus_type_id?: string | null;
  amount?: number | null;
  rate?: number | null;
  conditions: Record<string, unknown>;
  generation_mode: 'auto' | 'suggest';
  sort_order: number;
}

export interface SpecialPayrollDay {
  id?: string;
  day_date: string;
  kind: 'bridge' | 'christmas_week';
  label?: string | null;
}

export interface AstreintePresetResult {
  created_bonus_types: string[];
  created_rules: string[];
  skipped_existing: number;
}

export interface PayrollVariablePreviewItem {
  employee_id: string;
  first_name?: string;
  last_name?: string;
  rule_code?: string;
  rule_label?: string;
  amount: number;
  quantity: number;
  details?: PayrollVariablePreviewDetails;
}

export interface PayrollVariableGenerateResult {
  company_id: string;
  year: number;
  month: number;
  dry_run: boolean;
  preview: PayrollVariablePreviewItem[];
  written_count: number;
}

export async function listPayrollVariableRules(): Promise<PayrollVariableRule[]> {
  const { data } = await apiClient.get<PayrollVariableRule[]>(
    '/api/payroll-variables/rules',
  );
  return data;
}

export async function createPayrollVariableRule(
  payload: PayrollVariableRule,
): Promise<PayrollVariableRule> {
  const { data } = await apiClient.post<PayrollVariableRule>(
    '/api/payroll-variables/rules',
    payload,
  );
  return data;
}

export async function updatePayrollVariableRule(
  ruleId: string,
  payload: PayrollVariableRule,
): Promise<PayrollVariableRule> {
  const { data } = await apiClient.put<PayrollVariableRule>(
    `/api/payroll-variables/rules/${ruleId}`,
    payload,
  );
  return data;
}

export async function deletePayrollVariableRule(ruleId: string): Promise<void> {
  await apiClient.delete(`/api/payroll-variables/rules/${ruleId}`);
}

export async function applyAstreinteEquipesPreset(): Promise<AstreintePresetResult> {
  const { data } = await apiClient.post<AstreintePresetResult>(
    '/api/payroll-variables/rules/preset/astreinte-equipes',
  );
  return data;
}

export async function applyShiftTeamsPayrollPreset(): Promise<AstreintePresetResult> {
  const { data } = await apiClient.post<AstreintePresetResult>(
    '/api/payroll-variables/rules/preset/shift-teams-payroll',
  );
  return data;
}

export async function listSpecialPayrollDays(
  year?: number,
): Promise<SpecialPayrollDay[]> {
  const { data } = await apiClient.get<SpecialPayrollDay[]>(
    '/api/payroll-variables/special-days',
    { params: year != null ? { year } : undefined },
  );
  return data;
}

export async function createSpecialPayrollDay(
  payload: SpecialPayrollDay,
): Promise<SpecialPayrollDay> {
  const { data } = await apiClient.post<SpecialPayrollDay>(
    '/api/payroll-variables/special-days',
    payload,
  );
  return data;
}

export async function deleteSpecialPayrollDay(dayId: string): Promise<void> {
  await apiClient.delete(`/api/payroll-variables/special-days/${dayId}`);
}

export async function generatePayrollVariables(
  year: number,
  month: number,
  dryRun = false,
): Promise<PayrollVariableGenerateResult> {
  const { data } = await apiClient.post<PayrollVariableGenerateResult>(
    '/api/payroll-variables/generate',
    null,
    { params: { year, month, dry_run: dryRun } },
  );
  return data;
}
