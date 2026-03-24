/**
 * API client pour le module de simulation de paie
 */

import apiClient from './apiClient';

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

export interface ManualParams {
  statut?: 'Cadre' | 'Non-cadre';
  taux_prelevement_source?: number;
  salaire_base?: number;
  duree_hebdomadaire?: number;
}

export interface ScenarioParams {
  salaire_base_override?: number;
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
}

export interface ReverseCalculationResponse {
  brut_calcule: number;
  net_obtenu: number;
  ecart: number;
  iterations: number;
  convergence: boolean;
  bulletin_complet: any;
  cout_employeur: number;
}

export interface SimulationCreateRequest {
  employee_id: string;
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

export interface SimulationDetail {
  id: string;
  employee_id: string;
  company_id: string;
  month: number;
  year: number;
  simulation_type: string;
  scenario_name?: string;
  scenario_data: any;
  payslip_data: any;
  created_at: string;
  created_by?: string;
  updated_at: string;
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

export interface DifferenceItem {
  field: string;
  label: string;
  simulated_value: number;
  real_value: number;
  ecart: number;
  ecart_percent: number;
}

export interface ComparisonSummary {
  ecart_brut: number;
  ecart_cotisations: number;
  ecart_net: number;
  ecart_net_imposable: number;
  ecart_cout_employeur: number;
  nombre_differences: number;
}

export interface ComparisonResponse {
  differences: DifferenceItem[];
  summary: ComparisonSummary;
  ecart_total: number;
}

export interface PredefinedScenario {
  name: string;
  description: string;
  params: ScenarioParams;
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
 * Récupère les détails d'une simulation
 */
export const getSimulation = async (simulationId: string): Promise<SimulationDetail> => {
  const response = await apiClient.get(`/api/simulation/${simulationId}`);
  return response.data;
};

/**
 * Récupère les simulations d'un employé
 */
export const getEmployeeSimulations = async (
  employeeId: string,
  month?: number,
  year?: number
): Promise<SimulationInfo[]> => {
  const params: any = {};
  if (month !== undefined) params.month = month;
  if (year !== undefined) params.year = year;

  const response = await apiClient.get(`/api/simulation/employee/${employeeId}`, {
    params,
  });
  return response.data;
};

/**
 * Compare une simulation avec un bulletin réel
 */
export const compareSimulation = async (
  simulationId: string,
  payslipId: string
): Promise<ComparisonResponse> => {
  const response = await apiClient.post(`/api/simulation/${simulationId}/compare`, {
    payslip_id: payslipId,
  });
  return response.data;
};

/**
 * Supprime une simulation
 */
export const deleteSimulation = async (simulationId: string): Promise<void> => {
  await apiClient.delete(`/api/simulation/${simulationId}`);
};

/**
 * Récupère les scénarios prédéfinis pour un employé
 */
export const getPredefinedScenarios = async (
  employeeId: string
): Promise<PredefinedScenario[]> => {
  const response = await apiClient.get(
    `/api/simulation/predefined-scenarios/${employeeId}`
  );
  return response.data.scenarios;
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
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `simulation_${simulationId}.pdf`;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(url);
};

/**
 * Ouvre l'aperçu HTML d'une simulation dans un nouvel onglet
 */
export const previewSimulationHTML = (simulationId: string): void => {
  // Construire l'URL pour l'aperçu HTML
  const baseURL = apiClient.defaults.baseURL || '';
  const previewURL = `${baseURL}/api/simulation/${simulationId}/html`;

  // Ouvrir dans un nouvel onglet
  // Note: L'authentification sera gérée par les cookies de session
  window.open(previewURL, '_blank');
};
