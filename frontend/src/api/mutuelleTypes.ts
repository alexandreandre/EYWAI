// frontend/src/api/mutuelleTypes.ts

import apiClient from './apiClient';

export interface MutuelleType {
  id: string;
  company_id: string;
  libelle: string;
  montant_salarial: number;
  montant_patronal: number;
  part_patronale_soumise_a_csg: boolean;
  is_active: boolean;
  employee_ids?: string[]; // IDs des employés qui souscrivent à cette mutuelle
  created_at?: string;
  updated_at?: string;
  created_by?: string;
}

export interface MutuelleTypeCreate {
  libelle: string;
  montant_salarial: number;
  montant_patronal: number;
  part_patronale_soumise_a_csg?: boolean;
  is_active?: boolean;
  employee_ids?: string[]; // IDs des employés qui souscrivent à cette mutuelle
}

export interface MutuelleTypeUpdate {
  libelle?: string;
  montant_salarial?: number;
  montant_patronal?: number;
  part_patronale_soumise_a_csg?: boolean;
  is_active?: boolean;
  employee_ids?: string[]; // IDs des employés qui souscrivent à cette mutuelle
}

export const mutuelleTypesApi = {
  /**
   * Récupère toutes les formules de mutuelle de l'entreprise active
   */
  async getMutuelleTypes(): Promise<MutuelleType[]> {
    const response = await apiClient.get<MutuelleType[]>('/api/mutuelle-types');
    return response.data;
  },

  /**
   * Crée une nouvelle formule de mutuelle
   */
  async createMutuelleType(data: MutuelleTypeCreate): Promise<MutuelleType> {
    const response = await apiClient.post<MutuelleType>('/api/mutuelle-types', data);
    return response.data;
  },

  /**
   * Met à jour une formule de mutuelle
   */
  async updateMutuelleType(id: string, data: MutuelleTypeUpdate): Promise<MutuelleType> {
    const response = await apiClient.put<MutuelleType>(`/api/mutuelle-types/${id}`, data);
    return response.data;
  },

  /**
   * Supprime une formule de mutuelle
   */
  async deleteMutuelleType(id: string): Promise<void> {
    await apiClient.delete(`/api/mutuelle-types/${id}`);
  },
};
