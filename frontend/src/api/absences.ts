// Fichier : src/api/absences.ts (VERSION COMPLÈTE ET CORRIGÉE)

import { log } from '@/lib/logger';
import apiClient from './apiClient';

// --- INTERFACES DE BASE ---

export interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
  balances: AbsenceBalance[]; // <-- On ajoute les soldes ici
}

export type ArretType =
  | 'maladie_simple'
  | 'accident_travail'
  | 'maladie_professionnelle'
  | 'accident_trajet'
  | 'mi_temps_therapeutique'
  | 'ald'
  | 'rechute_at'
  | 'arret_exceptionnel';

// Interface principale, mise à jour pour utiliser 'selected_days'
export interface AbsenceRequest {
  id: string;
  created_at: string;
  employee_id: string;
  type: 'conge_paye' | 'rtt' | 'sans_solde' | 'repos_compensateur' | 'recuperation_modulation' | 'evenement_familial' | 'arret_maladie' | 'arret_at' | 'arret_paternite' | 'arret_maternite' | 'arret_maladie_pro';
  selected_days: string[]; // Tableau de dates au format 'YYYY-MM-DD'
  comment: string | null;
  status: 'pending' | 'validated' | 'rejected' | 'cancelled';
  manager_id: string | null;
  manager_approved_at?: string | null;
  manager_rejected_at?: string | null;
  manager_rejection_reason?: string | null;
  workflow_step?: string | null;
  attachment_url: string | null;
  filename: string | null;
  event_subtype?: string | null;
  /** Pour conge_paye: nombre de jours payés (reste = congé sans solde). */
  jours_payes?: number | null;
  arret_type?: ArretType | null;
  /** Statut attestation salaire / IJSS (API module Documents). */
  certificate_status?: 'generated' | 'not_required' | 'pending' | null;
  certificate_id?: string | null;
}

export interface AbsenceRequestWithEmployee extends AbsenceRequest {
  employee: SimpleEmployee;
  event_familial_cycles_consumed?: number | null;  // Visible RH : nb fois cet événement consommé entièrement
}

/** Ligne renvoyée par GET /api/absences/pending-manager-approval (ne pas confondre avec @/api/training). */
export interface AbsencePendingManagerItem extends AbsenceRequest {
  employee: Pick<SimpleEmployee, 'id' | 'first_name' | 'last_name'>;
}

export interface ManagerApprovalPayload {
  approved: boolean;
  rejection_reason?: string | null;
}

export interface AbsenceBalance {
  type: string;
  acquired: number;
  taken: number;
  remaining: number | 'N/A' | 'selon événement';
}

export interface EvenementFamilialEvent {
  code: string;
  libelle: string;
  duree_jours: number;
  type_jours: string;
  quota: number;
  solde_restant: number;
  taken: number;
  cycles_completed?: number;  // Nombre de fois que l'événement a été entièrement consommé
}

export interface EvenementFamilialQuotaResponse {
  events: EvenementFamilialEvent[];
}

export interface CalendarDay {
  jour: number;
  type: string;
  heures_prevues?: number | null;
}

// Interface pour la réponse de notre endpoint "tout-en-un"
export interface AbsencePageData {
    balances: AbsenceBalance[];
    calendar_days: CalendarDay[];
    history: AbsenceRequest[];
}

// --- FONCTIONS API ---

/**
 * (POUR LES RH) Récupère les demandes d'absence, potentiellement filtrées par statut.
 */
export const getAbsenceRequests = (status?: 'pending' | 'validated' | 'rejected') => {
  const params = status ? { status } : {};
  return apiClient.get<AbsenceRequestWithEmployee[]>('/api/absences', { params });
};

/** Absences d'un collaborateur (lecture seule, fiche RH). */
export const getAbsencesForEmployee = (employeeId: string) => {
  return apiClient.get<AbsenceRequest[]>(`/api/absences/employees/${employeeId}`);
};

/**
 * Demandes d'absence en attente de validation manager (entreprise active = session).
 * @param companyId utilisé pour la clé React Query / cohérence multi-entreprise côté UI.
 */
export const getPendingManagerApproval = (companyId: string) => {
  void companyId;
  return apiClient.get<AbsencePendingManagerItem[]>('/api/absences/pending-manager-approval');
};

export const managerApproveAbsence = (
  absenceId: string,
  companyId: string,
  data: ManagerApprovalPayload,
) => {
  void companyId;
  return apiClient.post<AbsenceRequest>(`/api/absences/${absenceId}/manager-approve`, data);
};

/**
 * (POUR LES RH) Met à jour le statut d'une demande.
 */
export const updateAbsenceRequestStatus = (
  id: string,
  status: 'validated' | 'rejected',
  subrogationActive?: boolean,
) => {
  const body: { status: string; subrogation_active?: boolean } = { status };
  if (subrogationActive !== undefined) {
    body.subrogation_active = subrogationActive;
  }
  return apiClient.patch(`/api/absences/requests/${id}/status`, body);
};

/**
 * (POUR L'EMPLOYÉ) Récupère TOUTES les données de la page absences en une seule fois.
 */
export const getAbsencePageData = (year: number, month: number) => {
  return apiClient.get<AbsencePageData>(`/api/absences/employees/me/page-data`, {
    params: { year, month },
  });
};

// Interface pour la création d'une demande
export interface AbsenceCreationPayload {
  employee_id: string;
  type: 'conge_paye' | 'rtt' | 'repos_compensateur' | 'recuperation_modulation' | 'evenement_familial' | 'arret_maladie' | 'arret_at' | 'arret_paternite' | 'arret_maternite' | 'arret_maladie_pro';
  selected_days: string[]; // Les dates seront formatées en 'YYYY-MM-DD'
  comment?: string | null;
  attachment_url?: string | null;
  filename?: string | null;
  event_subtype?: string | null; // Requis si type = evenement_familial
  arret_type?: ArretType | null;
}

/**
 * (POUR L'EMPLOYÉ) Récupère les événements familiaux disponibles avec quota et solde.
 */
export const getEvenementsFamiliaux = () => {
  return apiClient.get<EvenementFamilialQuotaResponse>('/api/absences/employees/me/evenements-familiaux');
};

/**
 * Récupère une URL signée du backend pour uploader un justificatif de congé.
 */
export const getUploadUrl = async (filename: string) => {
  const response = await apiClient.post<{ path: string; signedURL: string }>(
    '/api/absences/get-upload-url',
    { filename }
  );
  return response.data;
};

/**
 * Uploade le fichier directement vers le stockage Supabase via l'URL signée.
 */
export const uploadFile = async (signedUrl: string, file: File) => {
  try {
    const response = await fetch(signedUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': file.type,
      },
      body: file,
    });

    if (!response.ok) {
      const errorBody = await response.text();
      log.error(`[ERREUR UPLOAD] Statut: ${response.status}, Réponse: ${errorBody}`);
      throw new Error(`Échec de l'upload vers Supabase Storage. Statut: ${response.status}`);
    }

  } catch (error) {
    log.error("[ERREUR UPLOAD] Exception lors du fetch:", error);
    throw error;
  }
};

/**
 * (POUR L'EMPLOYÉ) Envoie une nouvelle demande d'absence au backend.
 */
export const createAbsenceRequest = (payload: AbsenceCreationPayload) => {
  return apiClient.post('/api/absences/requests', payload);
};

// =====================================================
// ATTESTATIONS DE SALAIRE
// =====================================================

export interface SalaryCertificate {
  id: string;
  employee_id: string;
  absence_request_id: string;
  company_id: string;
  storage_path: string;
  filename: string;
  generated_at: string;
  generated_by?: string | null;
  transmitted_to_cpam: boolean;
  transmission_date?: string | null;
  /** URL pour ouvrir le PDF dans le navigateur (visualisation) */
  view_url?: string;
  /** URL pour télécharger le PDF */
  download_url?: string;
}

/**
 * Génère manuellement une attestation de salaire pour un arrêt validé.
 */
export const generateSalaryCertificate = (absenceId: string) => {
  return apiClient.post<{ certificate_id: string; message: string }>(
    `/api/absences/${absenceId}/generate-certificate`
  );
};

/**
 * Récupère les informations de l'attestation de salaire pour un arrêt.
 */
export const getSalaryCertificate = (absenceId: string) => {
  return apiClient.get<SalaryCertificate>(`/api/absences/${absenceId}/certificate`);
};

/**
 * Télécharge le PDF de l'attestation de salaire.
 */
export const downloadSalaryCertificate = async (absenceId: string): Promise<Blob> => {
  const response = await apiClient.get(`/api/absences/${absenceId}/certificate/download`, {
    responseType: 'blob',
  });
  return response.data;
};

// =====================================================
// APERÇU MAINTIEN DE SALAIRE
// =====================================================

export type MaintenanceSubrogationMode =
  | 'when_maintien'
  | 'automatic'
  | 'at_mp_only'
  | 'per_case';

export interface MaintenancePreview {
  qualification: {
    carence_ss_jours: number;
    taux_ijss_base: number;
    est_at_mp: boolean;
    est_ald: boolean;
  };
  carence: {
    carence_ss_jours: number;
    carence_employeur_jours: number;
    motif_carence: string;
    est_continuite: boolean;
  };
  ijss: {
    ijss_theorique: number;
    ijss_journaliere: number;
    nb_jours_indemnises: number;
    taux_applique: number;
    salaire_journalier_base: number;
  };
  maintien: {
    maintien_applicable: boolean;
    taux_maintien: number;
    maintien_cible: number;
    maintien_verse: number;
    complement_employeur: number;
    nb_jours_maintien: number;
    conflit_convention: boolean;
    motif_non_maintien?: string;
    carence_employeur_jours?: number;
    duree_par_taux_jours?: number;
    duree_maintien_legale_jours?: number;
  };
  prevoyance: {
    prevoyance_declenchee: boolean;
    seuil_jours?: number | null;
    eligible?: boolean;
    taux_cible?: number | null;
    franchise_jours?: number | null;
    montant?: number;
    nb_jours?: number;
    motif?: string | null;
  };
  alertes: string[];
  subrogation_active: boolean;
  type_arret: string;
  anciennete_mois?: number;
  statut?: string;
  est_cadre?: boolean;
  /** Renseigné par l’API pour l’UI (paramétrage entreprise). */
  subrogation_mode?: MaintenanceSubrogationMode;
  maintien_eligible_seniority?: boolean;
}

/**
 * Aperçu calcul maintien / IJSS pour une absence (arrêt qualifié).
 * @param subrogationActive surcharge optionnelle (ex. mode subrogation « par cas »).
 */
export const getMaintenancePreview = (
  absenceId: string,
  subrogationActive?: boolean
) => {
  const params =
    subrogationActive === undefined ? {} : { subrogation_active: subrogationActive };
  return apiClient.get<MaintenancePreview>(
    `/api/absences/${absenceId}/maintenance-preview`,
    { params }
  );
};