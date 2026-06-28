import apiClient from './apiClient';
import type { MutuelleType } from './mutuelleTypes';

export interface PscSettings {
  company_id: string;
  mutuelle_organisme_label?: string | null;
  mutuelle_employee_self_service: boolean;
}

export interface EmployeeMutuelleOption {
  id: string;
  libelle: string;
  montant_salarial: number;
  montant_patronal: number;
  pack_couverture?: string | null;
  statut_categoriel?: string | null;
  organisme_label?: string | null;
  organisme_display?: string | null;
  note?: string | null;
  code_option_dsn?: string | null;
}

export interface EmployeeMutuelleChoices {
  organisme_label?: string | null;
  self_service_enabled: boolean;
  current_mutuelle_type_id?: string | null;
  options: EmployeeMutuelleOption[];
}

export async function getPscSettings(): Promise<PscSettings> {
  const response = await apiClient.get<PscSettings>('/api/psc-settings');
  return response.data;
}

export async function updatePscSettings(payload: Partial<PscSettings>): Promise<PscSettings> {
  const response = await apiClient.put<PscSettings>('/api/psc-settings', payload);
  return response.data;
}

export async function getAdminPscSettings(companyId: string): Promise<PscSettings> {
  const response = await apiClient.get<PscSettings>(
    `/api/super-admin/companies/${companyId}/psc-settings`,
  );
  return response.data;
}

export async function updateAdminPscSettings(
  companyId: string,
  payload: Partial<PscSettings>,
): Promise<PscSettings> {
  const response = await apiClient.put<PscSettings>(
    `/api/super-admin/companies/${companyId}/psc-settings`,
    payload,
  );
  return response.data;
}

export function pscSettingsClientForCompany(companyId?: string): {
  get: () => Promise<PscSettings>;
  update: (payload: Partial<PscSettings>) => Promise<PscSettings>;
} {
  if (!companyId) {
    return {
      get: getPscSettings,
      update: updatePscSettings,
    };
  }
  return {
    get: () => getAdminPscSettings(companyId),
    update: (payload) => updateAdminPscSettings(companyId, payload),
  };
}

export async function getMyMutuelleChoices(): Promise<EmployeeMutuelleChoices> {
  const response = await apiClient.get<EmployeeMutuelleChoices>('/api/me/mutuelle-choices');
  return response.data;
}

export async function setMyMutuelleChoice(mutuelleTypeId: string): Promise<EmployeeMutuelleChoices> {
  const response = await apiClient.put<EmployeeMutuelleChoices>('/api/me/mutuelle-choice', {
    mutuelle_type_id: mutuelleTypeId,
  });
  return response.data;
}

export type { MutuelleType };
