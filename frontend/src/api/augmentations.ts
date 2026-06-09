import apiClient from '@/api/apiClient';

export type PerimetreAugmentation = 'brut_seul' | 'brut_et_hs';
export type TypeAugmentation = 'pourcentage' | 'montant_fixe';

export type SimulationRequest = {
  type_augmentation: TypeAugmentation;
  valeur: number;
  effective_date: string;
  perimetre_augmentation?: PerimetreAugmentation;
};

/** Réponse backend (schéma Pydantic SimulationResultat). */
export type SimulationResultat = {
  ancien_salaire_brut: number;
  nouveau_salaire_brut: number;
  difference_brut: number;
  ancien_net_estime: number;
  nouveau_net_estime: number;
  difference_net: number;
  anciennes_charges_patronales: number;
  nouvelles_charges_patronales: number;
  difference_charges_patronales: number;
  cout_total_employeur_avant: number;
  cout_total_employeur_apres: number;
  difference_cout_employeur: number;
  taux_augmentation_reel: number;
  perimetre_augmentation: PerimetreAugmentation;
  a_hs_structurelles: boolean;
  ancien_base_35h: number;
  ancien_part_hs: number;
  nouveau_base_35h: number;
  nouveau_part_hs: number;
};

export type UpdateSalaryRequest = {
  nouveau_salaire: number;
  motif?: string;
  effective_date: string;
  type_augmentation?: TypeAugmentation;
  valeur_augmentation?: number;
  perimetre_augmentation?: PerimetreAugmentation;
};

export type SalaryHistoryEntry = {
  id: string;
  ancien_salaire: { valeur?: number } & Record<string, unknown>;
  nouveau_salaire: { valeur?: number } & Record<string, unknown>;
  motif?: string | null;
  effective_date: string;
  created_at: string;
};

export async function simulerAugmentation(
  employeeId: string,
  companyId: string,
  data: SimulationRequest,
): Promise<SimulationResultat> {
  const res = await apiClient.post<SimulationResultat>(
    `/api/employees/${employeeId}/simulate-augmentation`,
    data,
    { headers: { 'X-Active-Company': companyId } },
  );
  return res.data;
}

export async function appliquerAugmentation(
  employeeId: string,
  companyId: string,
  data: UpdateSalaryRequest,
): Promise<void> {
  await apiClient.put(`/api/employees/${employeeId}/salary`, data, {
    headers: { 'X-Active-Company': companyId },
  });
}

export async function getSalaryHistory(
  employeeId: string,
  companyId: string,
): Promise<SalaryHistoryEntry[]> {
  const res = await apiClient.get<SalaryHistoryEntry[]>(
    `/api/employees/${employeeId}/salary-history`,
    { headers: { 'X-Active-Company': companyId } },
  );
  return res.data ?? [];
}

export type FiltresCollectifs = {
  service_id?: string | null;
  statut?: string | null;
  contract_type?: string | null;
  anciennete_min_mois?: number | null;
  salaire_min?: number | null;
  salaire_max?: number | null;
};

export type SimulationCollectiveRequest = {
  filtres: FiltresCollectifs;
  type_augmentation: TypeAugmentation;
  valeur: number;
  effective_date: string;
  perimetre_augmentation?: PerimetreAugmentation;
};

export type EmployeSimule = {
  employee_id: string;
  nom_complet: string;
  poste: string | null;
  service_id: string | null;
  ancien_salaire_brut: number;
  nouveau_salaire_brut: number;
  difference_brut: number;
  taux_augmentation_reel: number;
  a_hs_structurelles?: boolean;
  ancien_base_35h?: number | null;
  ancien_part_hs?: number | null;
  nouveau_base_35h?: number | null;
  nouveau_part_hs?: number | null;
};

export type SimulationCollectiveResultat = {
  nb_employes: number;
  employes: EmployeSimule[];
  masse_salariale_avant: number;
  masse_salariale_apres: number;
  difference_masse_salariale: number;
  cout_charges_patronales_supplementaires: number;
  cout_total_supplementaire: number;
};

export type ApplicationCollectiveRequest = {
  employee_ids: string[];
  type_augmentation: TypeAugmentation;
  valeur: number;
  effective_date: string;
  motif?: string | null;
  perimetre_augmentation?: PerimetreAugmentation;
};

export type ApplicationCollectiveResultat = {
  nb_appliques: number;
  nb_erreurs: number;
  erreurs: string[];
};

export async function simulerAugmentationCollective(
  companyId: string,
  data: SimulationCollectiveRequest,
): Promise<SimulationCollectiveResultat> {
  const res = await apiClient.post<SimulationCollectiveResultat>(
    '/api/employees/simulate-augmentation-collective',
    data,
    { headers: { 'X-Active-Company': companyId } },
  );
  return res.data;
}

export async function appliquerAugmentationCollective(
  companyId: string,
  data: ApplicationCollectiveRequest,
): Promise<ApplicationCollectiveResultat> {
  const res = await apiClient.post<ApplicationCollectiveResultat>(
    '/api/employees/appliquer-augmentation-collective',
    data,
    { headers: { 'X-Active-Company': companyId } },
  );
  return res.data;
}

export type GenerationAvenantsLotRequest = {
  employee_ids: string[];
  effective_date: string;
  motif?: string;
  template_id?: string;
  nouveau_salaire_par_employe?: Record<string, number>;
};

export type GenerationAvenantsLotResultat = {
  nb_generes: number;
  nb_erreurs: number;
  document_ids: string[];
  erreurs: string[];
};

export async function genererAvenantsLot(
  companyId: string,
  data: GenerationAvenantsLotRequest,
): Promise<GenerationAvenantsLotResultat> {
  const res = await apiClient.post<GenerationAvenantsLotResultat>(
    '/api/employees/generer-avenants-lot',
    data,
    { headers: { 'X-Active-Company': companyId } },
  );
  return res.data;
}
