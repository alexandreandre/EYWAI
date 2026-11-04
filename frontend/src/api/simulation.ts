/**
 * API client pour le module de simulation de paie
 */

import apiClient from './apiClient';
import type { MaintenancePreview } from './absences';
import { downloadBlob, openBlobInNewTab } from '@/lib/downloadBlob';

// ============================================================================
// Types
// ============================================================================

export interface PrimeScenario {
  name: string;
  amount: number;
  is_socially_taxed?: boolean;
  is_taxable?: boolean;
}

export interface AbsenceScenario {
  type: string;
  heures?: number;
  jours?: number;
  description?: string;
}

export interface CongeScenario {
  type?: string;
  jours: number;
  date_debut?: string;
  date_fin?: string;
}

export interface ClassificationConventionnelle {
  groupe_emploi: string;
  classe_emploi: number;
  coefficient: number;
}

export interface ManualParams {
  statut?: 'Cadre' | 'Non-cadre';
  taux_prelevement_source?: number;
  salaire_base?: number;
  duree_hebdomadaire?: number;
  idcc?: string;
  collective_agreement_id?: string;
  convention_libelle?: string;
  classification_conventionnelle?: ClassificationConventionnelle;
  date_entree?: string;
  hire_date?: string;
}

export interface ScenarioParams {
  salaire_base_override?: number;
  apply_cc_minimum?: boolean;
  heures_travaillees?: number;
  heures_sup_25?: number;
  heures_sup_50?: number;
  primes?: PrimeScenario[];
  absences?: AbsenceScenario[];
  conges?: CongeScenario[];
  manual_params?: ManualParams;
}

export interface ReverseCalculationRequest {
  employee_id: string | null;
  net_target: number;
  net_type: 'net_a_payer' | 'net_imposable';
  month: number;
  year: number;
  options?: ScenarioParams;
  /**
   * « bulletin_entier » (par défaut) : le brut d'un bulletin dont le net vaut la
   * cible ; « prime » : le brut d'une prime qui ajoute la cible au net du
   * bulletin du mois du salarié (fenêtre des primes).
   */
  mode?: 'bulletin_entier' | 'prime';
  prime_soumise_a_cotisations?: boolean;
  prime_soumise_a_impot?: boolean;
}

export interface ReverseCalculationResponse {
  brut_calcule: number;
  net_obtenu: number;
  ecart: number;
  iterations: number;
  convergence: boolean;
  bulletin_complet: any;
  cout_employeur: number;
  /** Période du calcul (celle de l'écran). */
  month?: number;
  year?: number;
  /** Contrat retenu ; `type_contrat_par_defaut` : l'écran ne l'a pas donné (un CDI). */
  type_contrat?: string;
  type_contrat_par_defaut?: boolean;
  /** Mode « prime » : nets du bulletin du mois sans et avec la prime. */
  mode?: 'bulletin_entier' | 'prime';
  net_a_payer_sans_prime?: number;
  net_a_payer_avec_prime?: number;
}

export interface SimulationCreateRequest {
  employee_id: string | null;
  month: number;
  year: number;
  scenario_name?: string;
  scenario_data: ScenarioParams;
  prefill_from_real?: boolean;
}

export interface SimulationCreateResponse {
  simulation_id: string;
  payslip_data: any;
  pdf_url?: string;
}

export interface SimulationInfo {
  id: string;
  employee_id: string;
  month: number;
  year: number;
  simulation_type: string;
  scenario_name?: string;
  net_a_payer?: number;
  created_at: string;
}

export const SIMULATION_ARRET_MALADIE_TYPES = [
  'maladie_simple',
  'accident_travail',
  'maladie_professionnelle',
  'accident_trajet',
  'mi_temps_therapeutique',
  'ald',
  'rechute_at',
  'arret_exceptionnel',
] as const;

export type SimulationArretMaladieArretType = (typeof SIMULATION_ARRET_MALADIE_TYPES)[number];

export type SimulationStatut = 'Cadre' | 'Non-Cadre';

export interface SimulationArretMaladieParams {
  employee_id: string;
  duree_jours: number;
  arret_type: SimulationArretMaladieArretType;
  subrogation_active: boolean;
  /** Date ISO (YYYY-MM-DD) */
  date_debut: string;
  nombre_enfants: number;
  /** Overrides « what-if » optionnels (n'altèrent pas la fiche salarié). */
  salaire_base_override?: number | null;
  statut_override?: SimulationStatut | null;
  anciennete_mois_override?: number | null;
}

export interface SimulationArretMaladieSynthese {
  salaire_mensuel_base: number;
  /** Net avant impôt avec l'arrêt moins net sans l'arrêt, IJSS nettes comprises, sur toute la durée. */
  impact_net_salarie: number;
  /** Retenue des jours ouvrés d'arrêt, valorisés comme sur le bulletin. */
  salaire_perdu?: number;
  cout_employeur_complement: number;
  charges_patronales_estimees: number;
  cout_employeur_total: number;
  ijss_theorique: number;
  maintien_verse: number;
  prevoyance_montant: number;
}

export interface SimulationArretMaladieProfil {
  statut: string;
  est_cadre: boolean;
  anciennete_mois: number;
  anciennete_annees: number;
  duree_maintien_legale_jours: number;
  duree_par_taux_jours: number;
  carence_employeur_jours: number;
}

export interface SimulationArretMaladieResult {
  scenario: string;
  parametres: {
    duree_jours: number;
    arret_type: string;
    subrogation_active: boolean;
    date_debut: string;
    nombre_enfants: number;
    salaire_base_override?: number | null;
    statut_override?: SimulationStatut | null;
    anciennete_mois_override?: number | null;
  };
  profil: SimulationArretMaladieProfil;
  resultats_maintien: MaintenancePreview;
  synthese: SimulationArretMaladieSynthese;
  alertes: string[];
}

// ============================================================================
// API Functions
// ============================================================================

/**
 * Calcul inverse : détermine le brut nécessaire pour un net cible
 */
export const reverseCalculation = async (
  data: ReverseCalculationRequest
): Promise<ReverseCalculationResponse> => {
  const response = await apiClient.post('/api/simulation/reverse-calculation', data);
  return response.data;
};

/**
 * Crée une simulation de bulletin de paie
 */
export const createPayslipSimulation = async (
  data: SimulationCreateRequest
): Promise<SimulationCreateResponse> => {
  const response = await apiClient.post('/api/simulation/create-payslip', data);
  return response.data;
};

/**
 * Télécharge le PDF d'une simulation
 */
export const downloadSimulationPDF = async (simulationId: string): Promise<void> => {
  const response = await apiClient.get(`/api/simulation/${simulationId}/pdf`, {
    responseType: 'blob',
  });

  // Créer un lien de téléchargement
  const blob = new Blob([response.data], { type: 'application/pdf' });
  downloadBlob(blob, `simulation_${simulationId}.pdf`);
};

/**
 * Ouvre l'aperçu HTML d'une simulation dans un nouvel onglet
 */
/**
 * Simulation arrêt maladie (maintien / IJSS, cohérent moteur bulletin).
 */
export const simulerArretMaladie = async (
  params: SimulationArretMaladieParams
): Promise<SimulationArretMaladieResult> => {
  const response = await apiClient.post<SimulationArretMaladieResult>(
    '/api/simulation/arret-maladie',
    params
  );
  return response.data;
};
