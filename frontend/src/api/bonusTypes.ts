// frontend/src/api/bonusTypes.ts
import apiClient from './apiClient';

// --- INTERFACES ---
export interface BonusType {
  id: string;
  company_id: string;
  libelle: string;
  type: 'montant_fixe' | 'selon_heures';
  montant: number;
  seuil_heures?: number | null;
  soumise_a_cotisations: boolean;
  soumise_a_impot: boolean;
  prompt_ia?: string | null;
  created_at: string;
  updated_at: string;
  created_by?: string | null;
}

export interface BonusTypeCreate {
  libelle: string;
  type: 'montant_fixe' | 'selon_heures';
  montant: number;
  seuil_heures?: number | null;
  soumise_a_cotisations: boolean;
  soumise_a_impot: boolean;
  prompt_ia?: string | null;
}

export interface BonusTypeUpdate {
  libelle?: string;
  type?: 'montant_fixe' | 'selon_heures';
  montant?: number;
  seuil_heures?: number | null;
  soumise_a_cotisations?: boolean;
  soumise_a_impot?: boolean;
  prompt_ia?: string | null;
}

export interface BonusCalculationResult {
  amount: number;
  calculated: boolean;
  total_hours?: number;
  seuil?: number;
  condition_met?: boolean;
}

// --- FONCTIONS D'API ---

export const getBonusTypes = () => {
  return apiClient.get<BonusType[]>('/api/bonus-types');
};

export const createBonusType = (data: BonusTypeCreate) => {
  return apiClient.post<BonusType>('/api/bonus-types', data);
};

export const updateBonusType = (id: string, data: BonusTypeUpdate) => {
  return apiClient.put<BonusType>(`/api/bonus-types/${id}`, data);
};

export const deleteBonusType = (id: string) => {
  return apiClient.delete(`/api/bonus-types/${id}`);
};

export const calculateBonusAmount = (
  bonusTypeId: string,
  employeeId: string,
  year: number,
  month: number
) => {
  return apiClient.get<BonusCalculationResult>(
    `/api/bonus-types/calculate/${bonusTypeId}`,
    {
      params: { employee_id: employeeId, year, month }
    }
  );
};
