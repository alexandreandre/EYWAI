import apiClient from '@/api/apiClient';

export type PayrollVariableRuleType =
  | 'fixed_monthly'
  | 'per_astreinte_week'
  | 'per_shift_type'
  | 'per_modulation_payout'
  | 'per_night_hour';

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

export interface PayrollVariablePreviewItem {
  employee_id: string;
  first_name?: string;
  last_name?: string;
  rule_code?: string;
  rule_label?: string;
  amount: number;
  quantity: number;
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
