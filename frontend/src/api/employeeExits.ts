/**
 * API Client pour la gestion des sorties de salariés
 * Gère les démissions, ruptures conventionnelles et licenciements
 */

import apiClient from './apiClient';

// ============================================================================
// TYPES
// ============================================================================

export type ExitType = 'demission' | 'rupture_conventionnelle' | 'licenciement' | 'depart_retraite' | 'fin_periode_essai';

export type ExitStatus =
  // Démission
  | 'demission_recue'
  | 'demission_preavis_en_cours'
  | 'demission_effective'
  // Rupture conventionnelle
  | 'rupture_en_negociation'
  | 'rupture_validee'
  | 'rupture_homologuee'
  | 'rupture_effective'
  // Licenciement
  | 'licenciement_convocation'
  | 'licenciement_notifie'
  | 'licenciement_preavis_en_cours'
  | 'licenciement_effective'
  // Commun
  | 'archivee'
  | 'annulee';

export type DocumentType =
  // Documents uploadés
  | 'lettre_demission'
  | 'convention_rupture_signee'
  | 'lettre_licenciement'
  | 'accuse_reception'
  | 'convocation_entretien'
  | 'justificatif_autre'
  // Documents auto-générés
  | 'certificat_travail'
  | 'attestation_pole_emploi'
  | 'solde_tout_compte'
  | 'recu_solde_compte'
  | 'attestation_portabilite_mutuelle';

export interface SimpleEmployee {
  id: string;
  first_name: string;
  last_name: string;
  email?: string;
  job_title?: string;
}

export interface EmployeeExit {
  id: string;
  company_id: string;
  employee_id: string;

  // Type et statut
  exit_type: ExitType;
  status: ExitStatus;

  // Dates
  exit_request_date: string;
  notice_start_date?: string;
  notice_end_date?: string;
  last_working_day: string;
  final_settlement_date?: string;

  // Préavis
  notice_period_days: number;
  is_gross_misconduct: boolean;
  notice_indemnity_type?: string;

  // Détails
  exit_reason?: string;
  exit_notes?: Record<string, any>;

  // Calculs
  calculated_indemnities?: Record<string, any>;
  remaining_vacation_days?: number;
  final_net_amount?: number;

  // Workflow
  initiated_by?: string;
  validated_by?: string;
  validation_date?: string;
  archived_by?: string;
  archived_at?: string;

  // Métadonnées
  created_at: string;
  updated_at: string;
}

export interface EmployeeExitWithDetails extends EmployeeExit {
  employee?: any;
  documents?: ExitDocument[];
  checklist_items?: ChecklistItem[];
  checklist_completion_rate?: number;
}

export interface ExitDocument {
  id: string;
  exit_id: string;
  company_id: string;

  // Classification
  document_type: DocumentType;
  document_category: 'uploaded' | 'generated';

  // Stockage
  storage_path: string;
  filename: string;
  mime_type?: string;
  file_size_bytes?: number;

  // Génération
  generation_template?: string;
  generation_data?: Record<string, any>;
  generated_at?: string;

  // Upload
  uploaded_by?: string;
  upload_notes?: string;

  // Statut
  is_signed: boolean;
  signature_date?: string;
  is_transmitted: boolean;
  transmission_date?: string;

  // Publication vers l'espace collaborateur
  published_to_employee: boolean;
  published_at?: string;
  published_by?: string;

  // Métadonnées
  created_at: string;
  updated_at: string;

  // URL de téléchargement (ajoutée dynamiquement)
  download_url?: string;
}

export interface ExitDocumentDetails extends ExitDocument {
  document_data?: Record<string, any>;
  edit_history?: Array<Record<string, any>>;
  version: number;
  manually_edited: boolean;
  last_edited_by?: string;
  last_edited_at?: string;
}

export interface ExitDocumentEditRequest {
  document_data: Record<string, any>;
  changes_summary: string;
  internal_note?: string;
}

export interface ExitDocumentEditResponse {
  success: boolean;
  message: string;
  document_id: string;
  version: number;
  edited_at: string;
}

export interface ChecklistItem {
  id: string;
  exit_id: string;
  company_id: string;

  // Détails
  item_code: string;
  item_label: string;
  item_description?: string;
  item_category: 'administratif' | 'materiel' | 'acces' | 'legal' | 'autre';

  // Statut
  is_completed: boolean;
  completed_by?: string;
  completed_at?: string;
  completion_notes?: string;

  // Configuration
  is_required: boolean;
  due_date?: string;
  display_order: number;

  // Métadonnées
  created_at: string;
  updated_at: string;
}

export interface ExitIndemnityCalculation {
  exit_id: string;
  employee_id: string;

  // Ancienneté
  anciennete_annees: number;
  salaire_reference: number;

  // Indemnités détaillées
  indemnite_preavis: {
    montant: number;
    description: string;
    calcul: string;
  };
  indemnite_conges: {
    montant: number;
    description: string;
    calcul: string;
  };
  indemnite_licenciement?: {
    montant: number;
    description: string;
    calcul: string;
  };
  indemnite_rupture_conventionnelle?: {
    montant_negocie: number;
    description: string;
    calcul: string;
  };

  // Totaux
  total_gross_indemnities: number;
  total_net_indemnities: number;

  // Métadonnées
  calculation_date: string;
  calculation_details: Record<string, any>;
}

export interface CreateEmployeeExitRequest {
  employee_id: string;
  exit_type: ExitType;
  exit_request_date: string;
  last_working_day: string;
  exit_reason?: string;
  notice_period_days?: number;
  is_gross_misconduct?: boolean;
  notice_indemnity_type?: 'paid' | 'waived' | 'not_applicable';
}

export interface UpdateEmployeeExitRequest {
  status?: ExitStatus;
  notice_start_date?: string;
  notice_end_date?: string;
  last_working_day?: string;
  final_settlement_date?: string;
  exit_reason?: string;
  exit_notes?: Record<string, any>;
}

export interface StatusUpdateRequest {
  new_status: ExitStatus;
  notes?: string;
}

export interface DocumentUploadUrlRequest {
  filename: string;
  document_type: DocumentType;
  mime_type?: string;
}

export interface DocumentUploadUrlResponse {
  upload_url: string;
  storage_path: string;
  expires_in: number;
}

export interface CreateExitDocumentRequest {
  exit_id: string;
  document_type: DocumentType;
  storage_path: string;
  filename: string;
  mime_type?: string;
  file_size_bytes?: number;
  upload_notes?: string;
}

export interface CreateChecklistItemRequest {
  exit_id: string;
  item_code: string;
  item_label: string;
  item_description?: string;
  item_category: 'administratif' | 'materiel' | 'acces' | 'legal' | 'autre';
  is_required?: boolean;
  due_date?: string;
  display_order?: number;
}

export interface UpdateChecklistItemRequest {
  is_completed?: boolean;
  completion_notes?: string;
  due_date?: string;
}

// ============================================================================
// API FUNCTIONS - EMPLOYEE EXITS
// ============================================================================

/**
 * Liste toutes les sorties de l'entreprise active
 */
export async function getEmployeeExits(params?: {
  status?: string;
  exit_type?: string;
  employee_id?: string;
}): Promise<EmployeeExitWithDetails[]> {
  const response = await apiClient.get('/api/employee-exits', { params });
  return response.data;
}

/**
 * Récupère les détails d'une sortie
 */
export async function getEmployeeExit(exitId: string): Promise<EmployeeExitWithDetails> {
  const response = await apiClient.get(`/api/employee-exits/${exitId}`);
  return response.data;
}

/**
 * Crée un nouveau processus de sortie
 */
export async function createEmployeeExit(data: CreateEmployeeExitRequest): Promise<EmployeeExit> {
  const response = await apiClient.post('/api/employee-exits', data);
  return response.data;
}

/**
 * Met à jour une sortie
 */
export async function updateEmployeeExit(
  exitId: string,
  data: UpdateEmployeeExitRequest
): Promise<EmployeeExit> {
  const response = await apiClient.patch(`/api/employee-exits/${exitId}`, data);
  return response.data;
}

/**
 * Met à jour le statut d'une sortie
 */
export async function updateExitStatus(
  exitId: string,
  statusRequest: StatusUpdateRequest
): Promise<{ success: boolean; exit: EmployeeExit; message?: string }> {
  const response = await apiClient.patch(`/api/employee-exits/${exitId}/status`, statusRequest);
  return response.data;
}

/**
 * Supprime une sortie (admin seulement)
 */
export async function deleteEmployeeExit(exitId: string): Promise<void> {
  await apiClient.delete(`/api/employee-exits/${exitId}`);
}

// ============================================================================
// API FUNCTIONS - INDEMNITIES
// ============================================================================

/**
 * Calcule les indemnités de sortie
 */
export async function calculateExitIndemnities(exitId: string): Promise<ExitIndemnityCalculation> {
  const response = await apiClient.post(`/api/employee-exits/${exitId}/calculate-indemnities`);
  return response.data;
}

// ============================================================================
// API FUNCTIONS - DOCUMENTS
// ============================================================================

/**
 * Obtient une URL signée pour uploader un document
 */
export async function getDocumentUploadUrl(
  exitId: string,
  request: DocumentUploadUrlRequest
): Promise<DocumentUploadUrlResponse> {
  const response = await apiClient.post(`/api/employee-exits/${exitId}/documents/upload-url`, request);
  return response.data;
}

/**
 * Upload un fichier vers l'URL signée
 */
export async function uploadDocument(uploadUrl: string, file: File): Promise<void> {
  await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': file.type,
    },
  });
}

/**
 * Associe un document uploadé à une sortie
 */
export async function createExitDocument(data: CreateExitDocumentRequest): Promise<ExitDocument> {
  const response = await apiClient.post(`/api/employee-exits/${data.exit_id}/documents`, data);
  return response.data;
}

/**
 * Liste les documents d'une sortie
 */
export async function getExitDocuments(exitId: string): Promise<ExitDocument[]> {
  const response = await apiClient.get(`/api/employee-exits/${exitId}/documents`);
  return response.data;
}

/**
 * Génère automatiquement un document
 */
export async function generateExitDocument(
  exitId: string,
  documentType: 'certificat_travail' | 'attestation_pole_emploi' | 'solde_tout_compte'
): Promise<{ success: boolean; message: string; document_type: string }> {
  const response = await apiClient.post(`/api/employee-exits/${exitId}/documents/generate/${documentType}`);
  return response.data;
}

/**
 * Supprime un document
 */
export async function deleteExitDocument(exitId: string, documentId: string): Promise<void> {
  await apiClient.delete(`/api/employee-exits/${exitId}/documents/${documentId}`);
}

/**
 * Publie des documents de sortie vers l'espace Documents du salarié
 */
export interface PublishExitDocumentsRequest {
  document_ids?: string[];
  force_update?: boolean;
}

export interface PublishedDocumentStatus {
  exit_document_id: string;
  document_type: string;
  filename: string;
  status: 'published' | 'updated' | 'already_published' | 'failed' | 'file_missing';
  employee_document_id?: string;
  url?: string;
  error_message?: string;
  published_at?: string;
}

export interface PublishExitDocumentsResponse {
  exit_id: string;
  employee_id: string;
  success: boolean;
  documents: PublishedDocumentStatus[];
  total_published: number;
  total_updated: number;
  total_failed: number;
  total_already_published: number;
}

export async function publishExitDocuments(
  exitId: string,
  request: PublishExitDocumentsRequest = {}
): Promise<PublishExitDocumentsResponse> {
  const response = await apiClient.post<PublishExitDocumentsResponse>(
    `/api/employee-exits/${exitId}/documents/publish`,
    request
  );
  return response.data;
}

/**
 * Dépublie un document de sortie (le retire de l'espace collaborateur)
 */
export async function unpublishExitDocument(exitId: string, documentId: string): Promise<ExitDocument> {
  const response = await apiClient.post<ExitDocument>(
    `/api/employee-exits/${exitId}/documents/${documentId}/unpublish`
  );
  return response.data;
}

/**
 * Récupère les détails complets d'un document avec ses données éditables
 */
export async function getExitDocumentDetails(exitId: string, documentId: string): Promise<ExitDocumentDetails> {
  const response = await apiClient.get<ExitDocumentDetails>(
    `/api/employee-exits/${exitId}/documents/${documentId}/details`
  );
  return response.data;
}

/**
 * Édite un document de sortie et régénère le PDF
 */
export async function editExitDocument(
  exitId: string,
  documentId: string,
  editRequest: ExitDocumentEditRequest
): Promise<ExitDocumentEditResponse> {
  const response = await apiClient.post<ExitDocumentEditResponse>(
    `/api/employee-exits/${exitId}/documents/${documentId}/edit`,
    editRequest
  );
  return response.data;
}

/**
 * Récupère l'historique des modifications d'un document
 */
export async function getExitDocumentHistory(exitId: string, documentId: string): Promise<{
  document_id: string;
  total_versions: number;
  history: Array<{
    version: number;
    edited_by?: string;
    edited_at: string;
    changes_summary: string;
  }>;
}> {
  const response = await apiClient.get(
    `/api/employee-exits/${exitId}/documents/${documentId}/history`
  );
  return response.data;
}

// ============================================================================
// API FUNCTIONS - CHECKLIST
// ============================================================================

/**
 * Récupère la checklist d'une sortie
 */
export async function getExitChecklist(exitId: string): Promise<ChecklistItem[]> {
  const response = await apiClient.get(`/api/employee-exits/${exitId}/checklist`);
  return response.data;
}

/**
 * Ajoute un item à la checklist
 */
export async function addChecklistItem(data: CreateChecklistItemRequest): Promise<ChecklistItem> {
  const response = await apiClient.post(`/api/employee-exits/${data.exit_id}/checklist`, data);
  return response.data;
}

/**
 * Met à jour un item de checklist (marquer complété, etc.)
 */
export async function updateChecklistItem(
  exitId: string,
  itemId: string,
  data: UpdateChecklistItemRequest
): Promise<ChecklistItem> {
  const response = await apiClient.patch(`/api/employee-exits/${exitId}/checklist/${itemId}/complete`, data);
  return response.data;
}

/**
 * Supprime un item de checklist
 */
export async function deleteChecklistItem(exitId: string, itemId: string): Promise<void> {
  await apiClient.delete(`/api/employee-exits/${exitId}/checklist/${itemId}`);
}

// ============================================================================
// HELPER FUNCTIONS
// ============================================================================

export const exitTypeLabels: Record<ExitType, string> = {
  demission: 'Démission',
  rupture_conventionnelle: 'Rupture conventionnelle',
  licenciement: 'Licenciement',
  depart_retraite: 'Départ à la retraite',
  fin_periode_essai: 'Fin de période d\'essai',
};

export const statusLabels: Record<ExitStatus, string> = {
  // Démission
  demission_recue: 'Reçue',
  demission_preavis_en_cours: 'Préavis en cours',
  demission_effective: 'Effective',
  // Rupture conventionnelle
  rupture_en_negociation: 'En négociation',
  rupture_validee: 'Validée',
  rupture_homologuee: 'Homologuée',
  rupture_effective: 'Effective',
  // Licenciement
  licenciement_convocation: 'Convocation',
  licenciement_notifie: 'Notifié',
  licenciement_preavis_en_cours: 'Préavis en cours',
  licenciement_effective: 'Effective',
  // Commun
  archivee: 'Archivée',
  annulee: 'Annulée',
};

export const documentTypeLabels: Record<DocumentType, string> = {
  // Documents uploadés
  lettre_demission: 'Lettre de démission',
  convention_rupture_signee: 'Convention de rupture signée',
  lettre_licenciement: 'Lettre de licenciement',
  accuse_reception: 'Accusé de réception',
  convocation_entretien: 'Convocation à un entretien',
  justificatif_autre: 'Autre justificatif',
  // Documents auto-générés
  certificat_travail: 'Certificat de travail',
  attestation_pole_emploi: 'Attestation Pôle Emploi',
  solde_tout_compte: 'Solde de tout compte',
  recu_solde_compte: 'Reçu pour solde de tout compte',
  attestation_portabilite_mutuelle: 'Attestation de portabilité mutuelle',
};

export function getStatusVariant(status: ExitStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  if (status.includes('annulee')) return 'outline';
  if (status.includes('archivee')) return 'outline';
  if (status.includes('licenciement')) return 'destructive';
  if (status.includes('effective') || status.includes('homologuee')) return 'outline';
  if (status.includes('validee')) return 'default';
  return 'secondary';
}
