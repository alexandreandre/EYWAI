// Formules de prévoyance de la société active (02/11/2026).

import apiClient from './apiClient';

export type CategoriePrevoyance = 'cadre' | 'non_cadre' | 'tous';
export type BasePrevoyance = 'brut_plafonne' | 'tranche_2' | 'brut';

/** Une ligne, comme sur la fiche : taux en fraction. */
export interface LigneFormulePrevoyance {
  libelle: string;
  salarial: number;
  patronal: number;
  forfait_social: number;
  base?: BasePrevoyance | null;
  [cle: string]: unknown;
}

export interface FormulePrevoyance {
  id: string;
  company_id: string;
  libelle: string;
  statut_categoriel: CategoriePrevoyance;
  lignes: LigneFormulePrevoyance[];
  is_active: boolean;
}

export interface FormulePrevoyanceSaisie {
  libelle: string;
  statut_categoriel: CategoriePrevoyance;
  lignes: LigneFormulePrevoyance[];
}

export const CLE_FORMULES_PREVOYANCE = ['prevoyance-formules'] as const;

export const prevoyanceFormulesApi = {
  async lister(): Promise<FormulePrevoyance[]> {
    return (await apiClient.get<FormulePrevoyance[]>('/api/prevoyance-formules')).data;
  },
  async creer(saisie: FormulePrevoyanceSaisie): Promise<FormulePrevoyance> {
    return (await apiClient.post<FormulePrevoyance>('/api/prevoyance-formules', saisie)).data;
  },
  async modifier(
    id: string,
    saisie: Partial<FormulePrevoyanceSaisie>,
  ): Promise<{ formule: FormulePrevoyance; fiches_a_mettre_a_jour: number }> {
    return (await apiClient.put(`/api/prevoyance-formules/${id}`, saisie)).data;
  },
  async retirer(id: string): Promise<FormulePrevoyance> {
    return (await apiClient.delete<FormulePrevoyance>(`/api/prevoyance-formules/${id}`)).data;
  },
  async appliquer(id: string): Promise<{ fiches_mises_a_jour: number }> {
    return (await apiClient.post(`/api/prevoyance-formules/${id}/appliquer`)).data;
  },
};
