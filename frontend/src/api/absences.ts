// Fichier : src/api/absences.ts (VERSION COMPLÈTE ET CORRIGÉE)

import apiClient from './apiClient';

// --- INTERFACES DE BASE ---

export interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
  balances: AbsenceBalance[]; // <-- On ajoute les soldes ici
}

// Interface principale, mise à jour pour utiliser 'selected_days'
export interface AbsenceRequest {
  id: string;
  created_at: string;
  employee_id: string;
  type: 'conge_paye' | 'rtt' | 'sans_solde' | 'repos_compensateur' | 'evenement_familial' | 'arret_maladie' | 'arret_at' | 'arret_paternite' | 'arret_maternite' | 'arret_maladie_pro';
  selected_days: string[]; // Tableau de dates au format 'YYYY-MM-DD'
  comment: string | null;
  status: 'pending' | 'validated' | 'rejected' | 'cancelled';
  manager_id: string | null;
  attachment_url: string | null;
  filename: string | null;
  event_subtype?: string | null;
  /** Pour conge_paye: nombre de jours payés (reste = congé sans solde). */
  jours_payes?: number | null;
}

export interface AbsenceRequestWithEmployee extends AbsenceRequest {
  employee: SimpleEmployee;
  event_familial_cycles_consumed?: number | null;  // Visible RH : nb fois cet événement consommé entièrement
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

/**
 * (POUR LES RH) Met à jour le statut d'une demande.
 */
export const updateAbsenceRequestStatus = (id: string, status: 'validated' | 'rejected') => {
  return apiClient.patch(`/api/absences/requests/${id}/status`, { status });
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
  type: 'conge_paye' | 'rtt' | 'repos_compensateur' | 'evenement_familial' | 'arret_maladie' | 'arret_at' | 'arret_paternite' | 'arret_maternite' | 'arret_maladie_pro';
  selected_days: string[]; // Les dates seront formatées en 'YYYY-MM-DD'
  comment?: string | null;
  attachment_url?: string | null;
  filename?: string | null;
  event_subtype?: string | null; // Requis si type = evenement_familial
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
  console.log(`[DEBUG] Début de l'upload vers: ${signedUrl.split('?')[0]}...`);
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
      console.error(`[ERREUR UPLOAD] Statut: ${response.status}, Réponse: ${errorBody}`);
      throw new Error(`Échec de l'upload vers Supabase Storage. Statut: ${response.status}`);
    }

    console.log(`[DEBUG] Upload terminé avec succès. Statut: ${response.status}`);

  } catch (error) {
    console.error("[ERREUR UPLOAD] Exception lors du fetch:", error);
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