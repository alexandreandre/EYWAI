/**
 * API client — Plans de calendriers horaires prévisionnels + presets 2026.
 *
 * Endpoints RH (voir backend app/modules/schedules/api/router.py, router_rh) :
 *   GET/POST/PUT/DELETE /api/schedules/plans
 *   GET  /api/schedules/presets
 *   POST /api/schedules/presets/apply
 *   POST /api/schedules/generate
 */

import apiClient from './apiClient';

// ─── Types ──────────────────────────────────────────────────────────

export type ScopeType = 'company' | 'team' | 'service' | 'employees';
export type OverwriteMode = 'overwrite_all' | 'preserve_manual' | 'fill_empty';

export interface DayConfig {
  day: number; // 1 = lundi … 7 = dimanche
  type: string;
  hours: number;
  start?: string | null;
  end?: string | null;
  break_minutes?: number;
  break_paid?: boolean;
  comment?: string | null;
}

export interface SchedulePlan {
  id: string;
  company_id: string;
  name: string;
  scope_type: ScopeType;
  scope_ref: Record<string, unknown>;
  template_cycle: string[];
  cycle_anchor?: string | null;
  start_date: string;
  end_date?: string | null;
  overwrite_mode: OverwriteMode;
  status: 'draft' | 'applied';
  needs_confirmation: boolean;
  notes?: string | null;
  is_active: boolean;
}

export interface SchedulePlanUpsert {
  name: string;
  scope_type: ScopeType;
  scope_ref: Record<string, unknown>;
  template_cycle: string[];
  cycle_anchor?: string | null;
  start_date: string;
  end_date?: string | null;
  overwrite_mode: OverwriteMode;
  needs_confirmation?: boolean;
  notes?: string | null;
  is_active?: boolean;
}

export interface PresetTemplate {
  name: string;
  description: string;
  weekly_hours: number;
  day_configs: DayConfig[];
}

export interface PresetPlan {
  name: string;
  scope_type: ScopeType;
  employee_names: string[];
  template_names: string[];
  start_date: string;
  end_date?: string | null;
  cycle_anchor?: string | null;
  needs_confirmation: boolean;
  notes: string;
}

export interface Preset {
  key: string;
  company_label: string;
  templates: PresetTemplate[];
  plans: PresetPlan[];
}

export interface GenerateRequest {
  /** Omis = génère tous les plans actifs de la société (précédence de portée). */
  plan_id?: string;
  year?: number;
  overwrite_mode?: OverwriteMode;
  dry_run?: boolean;
  recalculate_payroll?: boolean;
}

export interface GenerationBatchResult {
  status: 'preview' | 'applied';
  company_id: string;
  plans_processed: number;
  employee_writes: number;
  plans: {
    plan_id: string;
    plan_name: string;
    scope_type: ScopeType;
    status: string;
    employee_count: number;
    reason?: string | null;
  }[];
}

export interface GenerationMonthSummary {
  year: number;
  month: number;
  weekly_totals: Record<string, number>;
  days: number;
}

export interface GenerationEmployeeSummary {
  employee_id: string;
  name: string;
  is_forfait: boolean;
  months: GenerationMonthSummary[];
}

export interface GenerationResult {
  status: 'preview' | 'applied' | 'skipped';
  dry_run?: boolean;
  reason?: string;
  plan_id?: string | null;
  overwrite_mode?: OverwriteMode;
  start_date?: string;
  end_date?: string;
  employee_count?: number;
  employees: GenerationEmployeeSummary[];
}

// ─── Calls ──────────────────────────────────────────────────────────

export async function listSchedulePlans(): Promise<SchedulePlan[]> {
  const { data } = await apiClient.get('/api/schedules/plans');
  return data;
}

export async function createSchedulePlan(payload: SchedulePlanUpsert): Promise<SchedulePlan> {
  const { data } = await apiClient.post('/api/schedules/plans', payload);
  return data;
}

export async function updateSchedulePlan(
  planId: string,
  payload: SchedulePlanUpsert,
): Promise<SchedulePlan> {
  const { data } = await apiClient.put(`/api/schedules/plans/${planId}`, payload);
  return data;
}

export async function deleteSchedulePlan(planId: string): Promise<void> {
  await apiClient.delete(`/api/schedules/plans/${planId}`);
}

export async function listSchedulePresets(): Promise<Preset[]> {
  const { data } = await apiClient.get('/api/schedules/presets');
  return data;
}

export async function applySchedulePreset(presetKey: string): Promise<{
  status: string;
  templates_created: number;
  plans_created: number;
  plans: SchedulePlan[];
}> {
  const { data } = await apiClient.post('/api/schedules/presets/apply', {
    preset_key: presetKey,
  });
  return data;
}

export async function generateSchedulePlan(payload: GenerateRequest): Promise<GenerationResult> {
  const { data } = await apiClient.post('/api/schedules/generate', payload);
  return data;
}

/** Génère (ou prévisualise) tous les plans actifs de la société en une passe. */
export async function generateAllSchedulePlans(payload: {
  year?: number;
  dry_run?: boolean;
  recalculate_payroll?: boolean;
}): Promise<GenerationBatchResult> {
  const { data } = await apiClient.post('/api/schedules/generate', payload);
  return data;
}
