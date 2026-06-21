import apiClient from '@/api/apiClient';

export type PreflightAnomalyType =
  | 'ecart_heures'
  | 'heures_non_saisies'
  | 'pointage'
  | 'conflit_absence'
  | 'hs_routing_pending'
  | 'hs_pointage_a_valider';

export type PreflightAnomalySeverity = 'bloquant' | 'a_verifier';

export type PreflightAnomalyStatus = 'a_traiter' | 'justifie' | 'resolu';

export type PreflightResolutionMotif =
  | 'directeur_site'
  | 'heures_sup'
  | 'erreur_pointage_corrigee'
  | 'autre';

export interface PreflightDayEcartDetail {
  jour: number;
  heures_prevues: number;
  heures_faites: number;
  ecart: number;
  heures_sup: boolean;
}

export interface PreflightAnomalyResolution {
  status: PreflightAnomalyStatus;
  motif?: PreflightResolutionMotif | null;
  commentaire?: string | null;
  resolved_by?: string | null;
  resolved_at?: string | null;
}

export interface PreflightAnomaly {
  id: string;
  employee_id: string;
  employee_name: string;
  team_id?: string | null;
  type: PreflightAnomalyType;
  severity: PreflightAnomalySeverity;
  status: PreflightAnomalyStatus;
  heures_prevues?: number | null;
  heures_faites?: number | null;
  ecart?: number | null;
  is_forfait_jour: boolean;
  sub_type?: string | null;
  detail_jours: PreflightDayEcartDetail[];
  conflict_days: number[];
  days_with_pointage_anomalies?: number | null;
  message?: string | null;
  resolution?: PreflightAnomalyResolution | null;
}

export interface PreflightAnomalyCounts {
  ecart_heures: number;
  heures_non_saisies: number;
  pointage: number;
  conflit_absence: number;
  hs_routing_pending: number;
  hs_pointage_a_valider: number;
  bloquant: number;
  a_verifier: number;
}

export interface PreflightAnomaliesResponse {
  year: number;
  month: number;
  total: number;
  total_open: number;
  total_treated: number;
  counts: PreflightAnomalyCounts;
  anomalies: PreflightAnomaly[];
}

export interface JustifyAnomalyPayload {
  employee_id: string;
  anomaly_type: PreflightAnomalyType;
  year: number;
  month: number;
  motif: PreflightResolutionMotif;
  commentaire?: string;
}

export interface RemoveAnomalyJustificationPayload {
  employee_id: string;
  anomaly_type: PreflightAnomalyType;
  year: number;
  month: number;
}

export interface AcknowledgePreflightPayload {
  year: number;
  month: number;
  open_anomalies_count: number;
  anomaly_types_summary: string[];
  commentaire?: string;
}

export async function getPreflightAnomalies(year: number, month: number) {
  const { data } = await apiClient.get<PreflightAnomaliesResponse>(
    '/api/payroll/preflight-anomalies',
    { params: { year, month } },
  );
  return data;
}

export async function justifyAnomaly(payload: JustifyAnomalyPayload) {
  const { data } = await apiClient.post<{ ok: boolean }>(
    '/api/payroll/preflight-anomalies/resolution',
    payload,
  );
  return data;
}

export async function removeAnomalyJustification(payload: RemoveAnomalyJustificationPayload) {
  const { data } = await apiClient.delete<{ ok: boolean }>(
    '/api/payroll/preflight-anomalies/resolution',
    { data: payload },
  );
  return data;
}

export async function acknowledgePreflight(payload: AcknowledgePreflightPayload) {
  const { data } = await apiClient.post<{ ok: boolean }>(
    '/api/payroll/preflight-anomalies/acknowledge',
    payload,
  );
  return data;
}
