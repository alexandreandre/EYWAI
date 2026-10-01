// frontend/src/api/payslips.ts

import apiClient from './apiClient';
import type { MaintenancePreview } from './absences';

// =====================================================
// TYPES
// =====================================================

/** Saisie « sur le net » déjà au mois suivant (montant négatif : retenue). */
export interface SaisieReportNetNegatif {
  id: string;
  name: string;
  amount: number;
}

/** GET /api/payslips/{id}/report-net-negatif */
export interface EtatReportNetNegatif {
  payslip_id: string;
  company_id: string;
  employee_id: string;
  annee: number;
  mois: number;
  net_a_payer: number | null;
  /** Positif quand le net est négatif, sinon 0. */
  montant_a_reporter: number;
  annee_suivante: number;
  mois_suivant: number;
  nom_du_report: string;
  /** Premier report reconnu, s'il y en a un. */
  saisie: SaisieReportNetNegatif | null;
  /** Tous les reports reconnus de ce bulletin (plusieurs = retenues cumulées). */
  saisies: SaisieReportNetNegatif[];
  /** Retenue « sur le net » qui n'est pas un report (acompte, etc.). */
  autre_retenue_sur_le_net: SaisieReportNetNegatif | null;
  verrou: 'bulletin_valide' | 'mois_cloture' | null;
}

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
  /** Heures sup déclarées depuis le bulletin, et celles que donnait le planning. */
  heures_sup_declarees?: { hs25: number; hs50: number; planning: number } | null;
  /** Le recalcul a échoué après la dernière correction : à régénérer avant validation. */
  recalcul_en_attente?: { depuis: string; erreur: string } | null;
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
  edited_by: string | null;
  edited_by_name: string | null;
  changes_summary: string;
  previous_payslip_data: any;
  /** Lien vers le PDF de cette version (signé à la lecture). */
  previous_pdf_url?: string | null;
  pdf_storage_path?: string | null;
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
  /** Points à arbitrer par la RH (plafond transport…) : pas des alertes, affichés discrètement. */
  points_a_arbitrer?: string[];
  /** « importe » : bulletin repris de l'ancien logiciel à la bascule — intouchable. */
  origine?: 'calcule' | 'importe' | string;
  /** true = calendrier ou absences changés depuis le calcul ; false = à jour ; null = inconnu. */
  a_recalculer?: boolean | null;
  salaire_brut?: number | null;
  heures_sup?: number | null;
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
  /** Dernière mise à jour, renvoyée avec une correction (refusée si elle a changé). */
  updated_at?: string | null;
  /** Le mois précédent a changé depuis le calcul : phrase à afficher, sinon null. */
  a_regenerer?: string | null;
  /** true = à recalculer ; false = à jour ; null = inconnu (pas d'empreinte). */
  a_recalculer?: boolean | null;
  /** Exports déjà faits pour le mois (vide pour le salarié). */
  exports_du_mois?: ExportDuMois[];
}

export interface ExportDuMois {
  type: string;
  libelle: string;
  date: string;
}

export interface PrimeAjoutee {
  name: string;
  amount: number;
  is_socially_taxed: boolean;
  is_taxable: boolean;
  catalog_prime_id: string | null;
}

/** Ce qui se corrige depuis le bulletin : ses variables du mois. */
export interface CorrectionsBulletin {
  heures_sup?: { hs25: number; hs50: number };
  revenir_au_planning?: boolean;
  primes_ajoutees?: PrimeAjoutee[];
  primes_corrigees?: Array<{ saisie_id: string; amount: number }>;
  primes_retirees?: string[];
}

/** Refus structuré du recalcul d'après une correction (même forme que le 422 de génération). */
export interface RecalculRefus {
  code: string;
  message: string;
  jours: Array<{ annee: number; mois: number; jour: number; heures: number }>;
}

export interface PayslipEditRequest {
  corrections: CorrectionsBulletin;
  changes_summary?: string;
  /** Absente : note inchangée ; chaîne vide : note effacée. */
  pdf_notes?: string;
  internal_note?: string;
  base_updated_at?: string;
}

export interface PayslipEditResponse {
  status: string;
  message: string;
  payslip: PayslipDetail;
  new_pdf_url?: string | null;
  /** Le moteur a recalculé le bulletin après les corrections. */
  recalcule: boolean;
  /** Présent si le moteur n'a pas pu recalculer : variables écrites, bulletin à régénérer. */
  recalcul_erreur?: string | null;
  /** Le refus complet quand le recalcul a été refusé par une garde ; `null` sinon. */
  recalcul_refus?: RecalculRefus | null;
}

export interface PayslipRestoreRequest {
  version: number;
}

export interface PayslipRestoreResponse {
  status: string;
  message: string;
  payslip: PayslipDetail;
  restored_version: number;
  recalcule: boolean;
  recalcul_erreur?: string | null;
  recalcul_refus?: RecalculRefus | null;
}

// =====================================================
// API FUNCTIONS
// =====================================================

/**
 * `X-Active-Company` d'une société connue de l'écran. Sans elle, l'intercepteur
 * prend celle du localStorage, qu'un autre onglet a pu changer : le backend
 * répondrait 404 sur un bulletin bien présent.
 */
export function enTeteSociete(companyId: string | null | undefined) {
  return companyId ? { headers: { 'X-Active-Company': companyId } } : undefined;
}

/** Report d'un net négatif sur le mois suivant : montant, saisie existante, verrou. */
export const getReportNetNegatif = async (
  payslipId: string,
  companyId?: string | null
): Promise<EtatReportNetNegatif> => {
  const response = await apiClient.get<EtatReportNetNegatif>(
    `/api/payslips/${payslipId}/report-net-negatif`,
    enTeteSociete(companyId)
  );
  return response.data;
};

/** Une lecture pour tous les bulletins du mois de paie. */
export const getReportsNetNegatifDuMois = async (
  year: number,
  month: number,
  companyId?: string | null
): Promise<EtatReportNetNegatif[]> => {
  const response = await apiClient.get<EtatReportNetNegatif[]>(
    '/api/payslips/reports-net-negatif',
    { ...enTeteSociete(companyId), params: { year, month } }
  );
  return response.data;
};

/** Création, mise à jour ou suppression du report (idempotente, verrou côté serveur). */
export const executerReportNetNegatif = async (
  payslipId: string,
  action: 'creer' | 'mettre_a_jour' | 'supprimer',
  companyId?: string | null
): Promise<EtatReportNetNegatif> => {
  const response = await apiClient.post<EtatReportNetNegatif>(
    `/api/payslips/${payslipId}/report-net-negatif`,
    { action },
    enTeteSociete(companyId)
  );
  return response.data;
};

/**
 * Récupère les détails complets d'un bulletin de paie
 */
export const getPayslipDetails = async (
  payslipId: string,
  companyId?: string | null
): Promise<PayslipDetail> => {
  const response = await apiClient.get<PayslipDetail>(
    `/api/payslips/${payslipId}`,
    enTeteSociete(companyId)
  );
  return response.data;
};

/**
 * Modifie un bulletin de paie
 */
export const editPayslip = async (
  payslipId: string,
  editRequest: PayslipEditRequest,
  companyId?: string | null
): Promise<PayslipEditResponse> => {
  const response = await apiClient.post<PayslipEditResponse>(
    `/api/payslips/${payslipId}/edit`,
    editRequest,
    enTeteSociete(companyId)
  );
  return response.data;
};

/**
 * Rend le bulletin enregistré, avec la note du PDF en cours de saisie.
 * Le HTML retourné est celui du PDF.
 */
export const previewPayslip = async (payslipId: string, pdfNotes?: string): Promise<string> => {
  const response = await apiClient.post<{ html: string }>(
    `/api/payslips/${payslipId}/preview`,
    { pdf_notes: pdfNotes ?? null }
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
  version: number,
  companyId?: string | null
): Promise<PayslipRestoreResponse> => {
  const response = await apiClient.post<PayslipRestoreResponse>(
    `/api/payslips/${payslipId}/restore`,
    { version },
    enTeteSociete(companyId)
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

const EN_TETE_DEJA_SUPPRIME = 'x-deja-supprime';

/** En-tête `X-Deja-Supprime` d'une 204 : le bulletin n'existait déjà plus. */
export function estDejaSupprime(headers: unknown): boolean {
  if (!headers || typeof headers !== 'object') return false;
  const lire = (headers as { get?: unknown }).get;
  if (typeof lire === 'function') {
    return String(lire.call(headers, EN_TETE_DEJA_SUPPRIME) ?? '') === 'true';
  }
  const cle = Object.keys(headers).find((k) => k.toLowerCase() === EN_TETE_DEJA_SUPPRIME);
  return cle !== undefined && String((headers as Record<string, unknown>)[cle]) === 'true';
}

/**
 * Supprime un bulletin de paie. Idempotent : un bulletin déjà supprimé
 * répond 204, avec `dejaSupprime`.
 *
 * `companyId` : la société que montre l'écran (voir `enTeteSociete`) ; sans
 * elle, le backend répondrait « déjà supprimé » pour un bulletin bien présent.
 */
export const deletePayslip = async (
  payslipId: string,
  companyId: string | null | undefined,
): Promise<{ dejaSupprime: boolean }> => {
  const response = await apiClient.delete(`/api/payslips/${payslipId}`, enTeteSociete(companyId));
  return { dejaSupprime: estDejaSupprime(response.headers) };
};

/**
 * Avertissement de génération : le backend mêle des chaînes (alertes RH du
 * moteur) et des objets `{ code, message }` (gardes forcées, ex.
 * `calendrier_incomplet_force`, `bulletin_valide_regenere`).
 */
/** `severity: 'info'` = point à arbitrer (plafond transport…) : affiché discrètement, hors du compte des alertes. */
export type PayslipGenerationWarning =
  | string
  | { code?: string; message?: string; severity?: 'info' | 'warning' };

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
  signal?: AbortSignal,
  companyId?: string | null
): Promise<{
  status: string;
  message: string;
  download_url: string;
  payslip_id?: string | null;
  warnings?: PayslipGenerationWarning[];
  salaire_brut?: number | null;
  net_a_payer?: number | null;
  heures_sup?: number | null;
}> => {
  const response = await apiClient.post('/api/actions/generate-payslip', data, {
    signal,
    ...enTeteSociete(companyId),
  });
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
export const validatePayslip = async (
  payslipId: string,
  companyId?: string | null
): Promise<PayslipDetail> => {
  const response = await apiClient.post<PayslipDetail>(
    `/api/payslips/${payslipId}/validate`,
    undefined,
    enTeteSociete(companyId)
  );
  return response.data;
};
