import apiClient from '@/api/apiClient';

export interface JeiSettings {
  id: string | null;
  company_id: string;
  jei_enabled: boolean;
  date_creation_etablissement: string | null;
  taux_exoneration: number;
  annees_restantes: number | null;
  date_fin_eligibilite: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export type JeiSettingsUpdate = Partial<
  Omit<
    JeiSettings,
    'id' | 'company_id' | 'annees_restantes' | 'date_fin_eligibilite' | 'created_at' | 'updated_at'
  >
>;

export async function getJeiSettings(): Promise<JeiSettings> {
  const response = await apiClient.get<JeiSettings>('/api/jei-settings/');
  return response.data;
}

export async function saveJeiSettings(data: JeiSettingsUpdate): Promise<JeiSettings> {
  const response = await apiClient.put<JeiSettings>('/api/jei-settings/', data);
  return response.data;
}
