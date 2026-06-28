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
  pack_couverture?: 'isole' | 'famille' | 'duo' | 'autre' | null;
  statut_categoriel?: 'cadre' | 'non_cadre' | 'tous';
  code_option_dsn?: string | null;
  code_organisme_dsn?: string | null;
  reference_contrat_dsn?: string | null;
  organisme_label?: string | null;
  note?: string | null;
  source?: 'manual' | 'dsn_import';
  employee_ids?: string[];
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
  pack_couverture?: 'isole' | 'famille' | 'duo' | 'autre' | null;
  statut_categoriel?: 'cadre' | 'non_cadre' | 'tous';
  code_option_dsn?: string | null;
  code_organisme_dsn?: string | null;
  reference_contrat_dsn?: string | null;
  organisme_label?: string | null;
  note?: string | null;
  employee_ids?: string[];
}

export interface MutuelleTypeUpdate {
  libelle?: string;
  montant_salarial?: number;
  montant_patronal?: number;
  part_patronale_soumise_a_csg?: boolean;
  is_active?: boolean;
  pack_couverture?: 'isole' | 'famille' | 'duo' | 'autre' | null;
  statut_categoriel?: 'cadre' | 'non_cadre' | 'tous';
  code_option_dsn?: string | null;
  code_organisme_dsn?: string | null;
  reference_contrat_dsn?: string | null;
  organisme_label?: string | null;
  note?: string | null;
  employee_ids?: string[];
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

function adminMutuelleBase(companyId: string): string {
  return `/api/super-admin/companies/${companyId}/mutuelle-types`;
}

/** Catalogue mutuelle — pilotage plateforme (fiche entreprise Super Admin). */
export const adminMutuelleTypesApi = {
  async getMutuelleTypes(companyId: string): Promise<MutuelleType[]> {
    const response = await apiClient.get<MutuelleType[]>(adminMutuelleBase(companyId));
    return response.data;
  },

  async createMutuelleType(
    companyId: string,
    data: MutuelleTypeCreate,
  ): Promise<MutuelleType> {
    const response = await apiClient.post<MutuelleType>(
      adminMutuelleBase(companyId),
      data,
    );
    return response.data;
  },

  async updateMutuelleType(
    companyId: string,
    id: string,
    data: MutuelleTypeUpdate,
  ): Promise<MutuelleType> {
    const response = await apiClient.put<MutuelleType>(
      `${adminMutuelleBase(companyId)}/${id}`,
      data,
    );
    return response.data;
  },

  async deleteMutuelleType(companyId: string, id: string): Promise<void> {
    await apiClient.delete(`${adminMutuelleBase(companyId)}/${id}`);
  },
};

export type MutuelleTypesClient = typeof mutuelleTypesApi;

export function mutuelleTypesClientForCompany(companyId?: string): {
  getMutuelleTypes: () => Promise<MutuelleType[]>;
  createMutuelleType: (data: MutuelleTypeCreate) => Promise<MutuelleType>;
  updateMutuelleType: (id: string, data: MutuelleTypeUpdate) => Promise<MutuelleType>;
  deleteMutuelleType: (id: string) => Promise<void>;
} {
  if (!companyId) {
    return mutuelleTypesApi;
  }
  return {
    getMutuelleTypes: () => adminMutuelleTypesApi.getMutuelleTypes(companyId),
    createMutuelleType: (data) => adminMutuelleTypesApi.createMutuelleType(companyId, data),
    updateMutuelleType: (id, data) =>
      adminMutuelleTypesApi.updateMutuelleType(companyId, id, data),
    deleteMutuelleType: (id) => adminMutuelleTypesApi.deleteMutuelleType(companyId, id),
  };
}
