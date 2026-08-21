// frontend/src/api/payslips.ts

import apiClient from './apiClient';
import type { MaintenancePreview } from './absences';

// =====================================================
// TYPES
// =====================================================

/** Ligne de détail brut (congés, absences, maintien arrêt maladie, etc.). */
export interface BulletinLigneBrut {
  libelle?: string | null;
  quantite?: number | null;
  taux?: number | null;
  gain?: number | null;
  perte?: number | null;
  is_arret_maladie?: boolean;
}

/** Rubrique officielle de cotisation (regroupement par risque). */
export interface CotisationRubriqueOfficielle {
  code: string;
  libelle: string;
  lignes: Record<string, unknown>[];
  total_salarial: number;
  total_patronal: number;
}

/** Synthèse net du bulletin (champs maintien ajoutés en T4B). */
export interface PayslipSyntheseNet {
  net_social_avant_impot?: number | null;
  montant_net_social?: number | null;
  net_imposable?: number | null;
  impot_prelevement_a_la_source?: {
    base?: number | null;
    taux?: number | null;
    montant?: number | null;
  } | null;
  remboursement_transport?: number | null;
  indemnite_transport_fixe?: number | null;
  acompte_verse?: number | null;
  ijss_subrogees?: number;
  ijss_brut?: number;
  ijss_net?: number;
  ijss_csg_total?: number;
  ijss_source?: 'theorique' | 'cpam_validated';
  maintien_employeur?: number;
  complement_employeur?: number;
  alertes_maintien?: string[];
  subrogation_active?: boolean;
}

/** Données JSON du bulletin (structure moteur paie + extensions). */
export interface PayslipBulletinData {
  en_tete?: Record<string, unknown>;
  details_conges?: BulletinLigneBrut[];
  details_absences?: BulletinLigneBrut[];
  details_maintien?: BulletinLigneBrut[];
  bloc_maintien?: MaintenancePreview;
  synthese_net?: PayslipSyntheseNet;
  calcul_du_brut?: BulletinLigneBrut[];
  structure_cotisations?: Record<string, unknown>;
  cotisations_officielles?: CotisationRubriqueOfficielle[];
  total_exonerations?: number;
  salaire_brut?: number;
  net_a_payer?: number;
  alertes_baremes?: Array<{
    code?: string;
    message?: string;
    critique?: boolean;
    severity?: string;
  }>;
  primes_non_soumises?: unknown[];
  notes_de_frais?: unknown[];
  arbitrage_conges?: string | null;
  pied_de_page?: Record<string, unknown>;
  [key: string]: unknown;
}

export function isPayslipBlocMaintienPresent(
  bloc: unknown
): bloc is MaintenancePreview {
  if (typeof bloc !== 'object' || bloc === null) return false;
  const o = bloc as Record<string, unknown>;
  return (
    typeof o.type_arret === 'string' &&
    o.qualification != null &&
    o.maintien != null &&
    o.ijss != null
  );
}

export interface InternalNote {
  id: string;
  author_id: string;
  author_name: string;
  timestamp: string;
  content: string;
}

export interface HistoryEntry {
  version: number;
  edited_at: string;
  edited_by: string;
  edited_by_name: string;
  changes_summary: string;
  previous_payslip_data: any;
  previous_pdf_url?: string;
}

export interface PayslipInfo {
  id: string;
  name: string;
  month: number;
  year: number;
  url: string;
  preview_url?: string;
  net_a_payer?: number;
  warnings?: string[];
  manually_edited: boolean;
  edit_count: number;
  edited_at?: string;
  edited_by?: string;
}

export type AlertLevel = 'CRITIQUE' | 'AVERTISSEMENT' | 'INFO';

export interface PayslipAlert {
  rule_id: string;
  level: AlertLevel;
  message: string;
  field: string;
  value_n: number;
  value_n1: number;
  delta_pct: number;
  status: 'active' | 'acquittee' | 'ignoree';
  acquitted_by?: string;
  acquitted_at?: string;
  comment?: string;
}

export interface ComparisonLine {
  libelle: string;
  value_n?: number;
  value_n1?: number;
  delta_abs?: number;
  delta_pct?: number;
  alert_level?: AlertLevel;
}

export interface ComparisonResult {
  bulletin_n_id: string;
  bulletin_n1_id?: string;
  month_n: number;
  year_n: number;
  month_n1?: number;
  year_n1?: number;
  lines: ComparisonLine[];
  alerts: PayslipAlert[];
  has_critical: boolean;
}

export interface TrendMonth {
  month: number;
  year: number;
  payslip_id: string;
  salaire_brut: number;
  net_a_payer: number;
  total_cotisations: number;
  alerts: PayslipAlert[];
}

export interface TrendResult {
  employee_id: string;
  months: TrendMonth[];
}

export interface PayslipDetail {
  id: string;
  employee_id: string;
  company_id: string;
  name: string;
  month: number;
  year: number;
  url: string;
  preview_url?: string;
  pdf_storage_path: string;
  payslip_data: PayslipBulletinData;
  manually_edited: boolean;
  edit_count: number;
  edited_at?: string;
  edited_by?: string;
  internal_notes: InternalNote[];
  pdf_notes?: string;
  edit_history: HistoryEntry[];
  cumuls?: any;
  status?: 'brouillon' | 'valide';
  validated_at?: string;
  validated_by?: string;
  period_edit_locked?: boolean;
  manual_edit_locked?: boolean;
  manual_edit_lock_reason?: string | null;
  manual_edit_lock_until?: string | null;
}

export interface PayslipEditRequest {
  payslip_data: PayslipBulletinData;
  changes_summary: string;
  pdf_notes?: string;
  internal_note?: string;
}

export interface PayslipEditResponse {
  status: string;
  message: string;
  payslip: PayslipDetail;
  new_pdf_url: string;
}

export interface PayslipRestoreRequest {
  version: number;
}

export interface PayslipRestoreResponse {
  status: string;
  message: string;
  payslip: PayslipDetail;
  restored_version: number;
}

// =====================================================
// API FUNCTIONS
// =====================================================

/**
 * Récupère les détails complets d'un bulletin de paie
 */
export const getPayslipDetails = async (payslipId: string): Promise<PayslipDetail> => {
  const response = await apiClient.get<PayslipDetail>(`/api/payslips/${payslipId}`);
  return response.data;
};

/**
 * Modifie un bulletin de paie
 */
export const editPayslip = async (
  payslipId: string,
  editRequest: PayslipEditRequest
): Promise<PayslipEditResponse> => {
  const response = await apiClient.post<PayslipEditResponse>(
    `/api/payslips/${payslipId}/edit`,
    editRequest
  );
  return response.data;
};

/**
 * Rend un bulletin à partir des données éditées, sans rien enregistrer.
 * Le HTML retourné est exactement celui du PDF qui sera généré.
 */
export const previewPayslip = async (
  payslipId: string,
  payslipData: unknown,
  pdfNotes?: string
): Promise<string> => {
  const response = await apiClient.post<{ html: string }>(
    `/api/payslips/${payslipId}/preview`,
    { payslip_data: payslipData, pdf_notes: pdfNotes ?? null }
  );
  return response.data.html;
};

/**
 * Récupère l'historique des modifications d'un bulletin
 */
export const getPayslipHistory = async (payslipId: string): Promise<HistoryEntry[]> => {
  const response = await apiClient.get<HistoryEntry[]>(`/api/payslips/${payslipId}/history`);
  return response.data;
};

/**
 * Restaure une version précédente d'un bulletin
 */
export const restorePayslipVersion = async (
  payslipId: string,
  version: number
): Promise<PayslipRestoreResponse> => {
  const response = await apiClient.post<PayslipRestoreResponse>(
    `/api/payslips/${payslipId}/restore`,
    { version }
  );
  return response.data;
};

/**
 * Récupère la liste des bulletins de l'utilisateur connecté
 */
export const getMyPayslips = async (): Promise<PayslipInfo[]> => {
  const response = await apiClient.get<PayslipInfo[]>('/api/me/payslips');
  return response.data;
};

/**
 * Récupère la liste des bulletins d'un employé
 */
export const getEmployeePayslips = async (employeeId: string): Promise<PayslipInfo[]> => {
  const response = await apiClient.get<PayslipInfo[]>(`/api/employees/${employeeId}/payslips`);
  return response.data;
};

/**
 * Supprime un bulletin de paie
 */
export const deletePayslip = async (payslipId: string): Promise<void> => {
  await apiClient.delete(`/api/payslips/${payslipId}`);
};

/**
 * Avertissement de génération : le backend mêle des chaînes (alertes RH du
 * moteur) et des objets `{ code, message }` (gardes forcées, ex.
 * `calendrier_incomplet_force`, `bulletin_valide_regenere`).
 */
export type PayslipGenerationWarning = string | { code?: string; message?: string };

/**
 * Génère un nouveau bulletin de paie.
 *
 * Sans flag, le backend refuse avec un `detail` structuré `{ code, message }` :
 * 422 `calendrier_incomplet` ou 409 `bulletin_valide`. Les flags de forçage ne
 * doivent être envoyés qu'après une confirmation explicite de l'utilisateur.
 */
export const generatePayslip = async (
  data: {
    employee_id: string;
    year: number;
    month: number;
    /** Génère malgré un calendrier incomplet (sinon 422 `calendrier_incomplet`). */
    force_calendrier_incomplet?: boolean;
    /** Régénère un bulletin validé en l'archivant (sinon 409 `bulletin_valide`). */
    regenerer_bulletin_valide?: boolean;
  },
  signal?: AbortSignal
): Promise<{
  status: string;
  message: string;
  download_url: string;
  payslip_id?: string | null;
  warnings?: PayslipGenerationWarning[];
}> => {
  const response = await apiClient.post('/api/actions/generate-payslip', data, { signal });
  return response.data;
};

/** Comparaison N vs dernier bulletin N-1 validé */
export const getComparison = async (payslipId: string): Promise<ComparisonResult> => {
  const response = await apiClient.get<ComparisonResult>(`/api/payslips/${payslipId}/comparison`);
  return response.data;
};

/** Tendance sur les bulletins validés précédant la période du bulletin */
export const getTrend = async (payslipId: string): Promise<TrendResult> => {
  const response = await apiClient.get<TrendResult>(`/api/payslips/${payslipId}/trend`);
  return response.data;
};

export const acquitAlert = async (
  payslipId: string,
  ruleId: string,
  comment?: string
): Promise<void> => {
  await apiClient.post(`/api/payslips/${payslipId}/alerts/${encodeURIComponent(ruleId)}/acquit`, {
    comment: comment ?? null,
  });
};

export const ignoreAlert = async (payslipId: string, ruleId: string): Promise<void> => {
  await apiClient.post(
    `/api/payslips/${payslipId}/alerts/${encodeURIComponent(ruleId)}/ignore`,
    {}
  );
};

/** Valide le bulletin (RH). Échoue en 400 si alertes critiques actives. */
export const validatePayslip = async (payslipId: string): Promise<PayslipDetail> => {
  const response = await apiClient.post<PayslipDetail>(`/api/payslips/${payslipId}/validate`);
  return response.data;
};
