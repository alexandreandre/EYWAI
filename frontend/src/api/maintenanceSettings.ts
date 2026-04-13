import apiClient from '@/api/apiClient';

export type SubrogationMode = 'automatic' | 'at_mp_only' | 'per_case';

export interface MaintenanceSettings {
  id: string | null;
  company_id: string;
  apply_legal_maintenance: boolean;
  min_seniority_months: number;
  employer_waiting_days: number;
  seniority_extension_enabled: boolean;
  remove_employer_waiting: boolean;
  annual_unique_waiting: boolean;
  maintain_100_percent: boolean;
  differentiated_at_illness: boolean;
  maintain_by_category: boolean;
  no_seniority_condition: boolean;
  custom_duration_days: number | null;
  subrogation_mode: SubrogationMode;
  provident_relay_days: number | null;
  created_at: string | null;
  updated_at: string | null;
}

export type MaintenanceSettingsUpdate = Partial<
  Omit<MaintenanceSettings, 'id' | 'company_id' | 'created_at' | 'updated_at'>
>;

export async function getMaintenanceSettings(): Promise<MaintenanceSettings> {
  const response = await apiClient.get<MaintenanceSettings>('/api/maintenance-settings/');
  return response.data;
}

export async function saveMaintenanceSettings(
  data: MaintenanceSettingsUpdate
): Promise<MaintenanceSettings> {
  const response = await apiClient.put<MaintenanceSettings>('/api/maintenance-settings/', data);
  return response.data;
}
