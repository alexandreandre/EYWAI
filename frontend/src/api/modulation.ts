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
