// frontend/src/api/collectiveAgreements.ts

import apiClient from './apiClient';

// =====================================================================
// TYPES - CATALOGUE
// =====================================================================

export interface CollectiveAgreementCatalog {
  id: string;
  created_at: string;
  updated_at: string;
  name: string;
  idcc: string;
  description?: string | null;
  sector?: string | null;
  effective_date?: string | null;
  rules_pdf_path?: string | null;
  rules_pdf_filename?: string | null;
  rules_pdf_url?: string | null; // URL signée générée par le backend
  is_active: boolean;
}

// =====================================================================
// TYPES - ASSIGNATION
// =====================================================================

export interface CompanyCollectiveAgreementWithDetails {
  id: string;
  company_id: string;
  collective_agreement_id: string;
  assigned_at: string;
  assigned_by?: string | null;
  agreement_details: CollectiveAgreementCatalog;
}

// =====================================================================
// API - CATALOGUE (lecture pour tous)
// =====================================================================

/**
 * Liste toutes les conventions du catalogue (pour le dropdown)
 */
export const getCatalog = (params?: {
  sector?: string;
  search?: string;
  active_only?: boolean;
}) => {
  return apiClient.get<CollectiveAgreementCatalog[]>('/api/collective-agreements/catalog', {
    params
  });
};

/**
 * Récupère une convention du catalogue par son ID
 */
export const getCatalogItem = (agreementId: string) => {
  return apiClient.get<CollectiveAgreementCatalog>(`/api/collective-agreements/catalog/${agreementId}`);
};

export interface ClassificationConventionnelle {
  groupe_emploi: string;
  classe_emploi: number;
  coefficient: number;
}

export interface SalaryMinimumRow {
  coefficient: number;
  valeur: number;
  libelle?: string | null;
}

/**
 * Récupère la grille de classification pour une convention collective
 */
export const getClassifications = (agreementId: string) => {
  return apiClient.get<ClassificationConventionnelle[]>(`/api/collective-agreements/catalog/${agreementId}/classifications`);
};

/**
 * Récupère les minima salariaux CC (coefficient → € mensuel).
 */
export const getSalaryMinima = (agreementId: string, codePostal?: string) => {
  return apiClient.get<SalaryMinimumRow[]>(
    `/api/collective-agreements/catalog/${agreementId}/salary-minima`,
    { params: codePostal ? { code_postal: codePostal } : undefined }
  );
};

// =====================================================================
// API - DOCUMENTS PDF (texte intégral + synthèse IA)
// =====================================================================

/**
 * Télécharge le PDF du texte intégral de la convention (blob).
 */
export const getConventionFullTextPdf = (agreementId: string) => {
  return apiClient.get<Blob>(
    `/api/collective-agreements/catalog/${agreementId}/document/full-text`,
    { responseType: 'blob' }
  );
};

/**
 * Télécharge le PDF de synthèse pédagogique (IA) de la convention (blob).
 */
export const getConventionSynthesisPdf = (agreementId: string) => {
  return apiClient.get<Blob>(
    `/api/collective-agreements/catalog/${agreementId}/document/synthesis`,
    { responseType: 'blob' }
  );
};

// =====================================================================
// API - ASSIGNATION (RH/Admin)
// =====================================================================

function companyScopeHeaders(companyId?: string) {
  return companyId ? { 'X-Active-Company': companyId } : undefined;
}

/**
 * Récupère toutes les conventions assignées à une entreprise.
 * Passer `companyId` pour cibler une filiale (admin groupe ou super admin).
 */
export const getMyCompanyAgreements = (companyId?: string) => {
  return apiClient.get<CompanyCollectiveAgreementWithDetails[]>(
    '/api/collective-agreements/my-company',
    { headers: companyScopeHeaders(companyId) }
  );
};

/**
 * Assigne une convention à une entreprise.
 * Passer `companyId` pour assigner à une filiale (admin groupe ou super admin).
 */
export const assignAgreement = (collectiveAgreementId: string, companyId?: string) => {
  return apiClient.post(
    '/api/collective-agreements/assign',
    { collective_agreement_id: collectiveAgreementId },
    { headers: companyScopeHeaders(companyId) }
  );
};

/**
 * Retire une convention d'une entreprise.
 * Passer `companyId` si l'entreprise cible diffère de l'entreprise active.
 */
export const unassignAgreement = (assignmentId: string, companyId?: string) => {
  return apiClient.delete(`/api/collective-agreements/unassign/${assignmentId}`, {
    headers: companyScopeHeaders(companyId),
  });
};

// =====================================================================
// API - SUPER ADMIN (gestion du catalogue)
// =====================================================================

export interface CreateCatalogItemInput {
  name: string;
  idcc: string;
  description?: string;
  sector?: string;
  effective_date?: string;
  is_active?: boolean;
}

export interface UpdateCatalogItemInput {
  name?: string;
  idcc?: string;
  description?: string;
  sector?: string;
  effective_date?: string;
  rules_pdf_path?: string;
  rules_pdf_filename?: string;
  is_active?: boolean;
}

export interface UploadUrlResponse {
  upload_url: string;
  file_path: string;
}

/**
 * Crée une nouvelle convention dans le catalogue (super admin uniquement)
 */
export const createCatalogItem = (data: CreateCatalogItemInput) => {
  return apiClient.post<CollectiveAgreementCatalog>('/api/collective-agreements/catalog', data);
};

/**
 * Met à jour une convention du catalogue (super admin uniquement)
 */
export const updateCatalogItem = (agreementId: string, data: UpdateCatalogItemInput) => {
  return apiClient.patch<CollectiveAgreementCatalog>(
    `/api/collective-agreements/catalog/${agreementId}`,
    data
  );
};

/**
 * Supprime une convention du catalogue (super admin uniquement)
 */
export const deleteCatalogItem = (agreementId: string) => {
  return apiClient.delete(`/api/collective-agreements/catalog/${agreementId}`);
};

/**
 * Génère une URL signée pour uploader un PDF (super admin uniquement)
 */
export const getUploadUrl = (filename: string) => {
  return apiClient.post<{ path: string; signedURL: string }>('/api/collective-agreements/catalog/upload-url', {
    filename
  });
};

/**
 * Upload un fichier PDF vers une URL signée
 */
export const uploadPdfToSignedUrl = async (uploadUrl: string, file: File) => {
  const response = await fetch(uploadUrl, {
    method: 'PUT',
    body: file,
    headers: {
      'Content-Type': 'application/pdf',
    },
  });

  if (!response.ok) {
    throw new Error('Échec du téléchargement du fichier');
  }

  return response;
};

// =====================================================================
// API - SUPER ADMIN (vue des assignations par entreprise)
// =====================================================================

export interface CompanyWithAssignments {
  id: string;
  company_name: string;
  assigned_agreements: CompanyCollectiveAgreementWithDetails[];
}

/**
 * Récupère toutes les assignations de conventions par entreprise (super admin uniquement)
 */
export const getAllCompanyAssignments = () => {
  return apiClient.get<CompanyWithAssignments[]>('/api/collective-agreements/all-assignments');
};

// =====================================================================
// API - CHAT IA (RH/Admin)
// =====================================================================

export interface AskQuestionRequest {
  agreement_id: string;
  question: string;
}

export interface AskQuestionResponse {
  answer: string;
  agreement_name: string;
}

/**
 * Pose une question à l'IA spécialisée sur une convention collective
 */
export const askQuestion = (data: AskQuestionRequest) => {
  return apiClient.post<AskQuestionResponse>('/api/collective-agreements-chat/ask', data);
};

// =====================================================================
// API - RÈGLES PAIE (extraction IA, super admin)
// =====================================================================

/**
 * Importe une convention depuis Légifrance (KALI) par IDCC
 */
export const importFromLegifrance = (
  data: {
    idcc: string;
    extract_rules?: boolean;
    sector?: string;
  },
  options?: { signal?: AbortSignal }
) => {
  return apiClient.post<KaliImportResponse>(
    '/api/collective-agreements/catalog/import-legifrance',
    data,
    { signal: options?.signal }
  );
};

/**
 * Import batch depuis Légifrance
 */
export const importFromLegifranceBatch = (data: {
  idcc_list?: string[];
  priority_only?: boolean;
  extract_rules?: boolean;
}) => {
  return apiClient.post<KaliImportBatchResponse>(
    '/api/collective-agreements/catalog/import-legifrance/batch',
    data
  );
};

/**
 * Synchronise toutes les CC actives du catalogue depuis Légifrance
 */
export const syncCatalogFromLegifrance = (
  data?: { extract_rules?: boolean },
  options?: { signal?: AbortSignal }
) => {
  return apiClient.post<KaliImportBatchResponse>(
    '/api/collective-agreements/catalog/sync-legifrance',
    data ?? {},
    { signal: options?.signal }
  );
};

/**
 * Ré-import Légifrance pour une fiche existante
 */
export const reimportFromLegifrance = (
  agreementId: string,
  extractRules = true,
  options?: { signal?: AbortSignal }
) => {
  return apiClient.post<KaliImportResponse>(
    `/api/collective-agreements/catalog/${agreementId}/import-legifrance`,
    null,
    { params: { extract_rules: extractRules }, signal: options?.signal }
  );
};

/**
 * Demande l'arrêt d'un import ou d'une sync Légifrance en cours
 */
export const cancelKaliImport = (data: { idcc?: string; catalog_sync?: boolean }) => {
  return apiClient.post<{ success: boolean; message: string }>(
    '/api/collective-agreements/catalog/kali-import/cancel',
    {
      idcc: data.idcc,
      catalog_sync: data.catalog_sync ?? false,
    }
  );
};

export interface KaliImportResponse {
  success: boolean;
  idcc: string;
  agreement_id?: string | null;
  title?: string | null;
  legifrance_url?: string | null;
  character_count?: number;
  created?: boolean;
  text_changed?: boolean;
  rules_skipped?: boolean;
  cancelled?: boolean;
  error?: string | null;
  rules?: {
    success: boolean;
    error?: string | null;
    confidence?: string | null;
  } | null;
}

export interface KaliImportBatchResponse {
  results: KaliImportResponse[];
  total: number;
  succeeded: number;
  failed: number;
  updated?: number;
  unchanged?: number;
  cancelled?: number;
}

export interface ExtractRulesResponse {
  success: boolean;
  idcc: string;
  agreement_id?: string | null;
  rules?: Record<string, unknown> | null;
  error?: string | null;
  tokens_used?: number;
  confidence?: string | null;
  log_id?: string | null;
}

export interface ExtractRulesBatchResponse {
  results: ExtractRulesResponse[];
  total: number;
  succeeded: number;
  failed: number;
}

export interface RulesStatusResponse {
  idcc: string;
  agreement_id: string;
  has_rules: boolean;
  rules?: Record<string, unknown> | null;
  source_text_hash?: string | null;
  extracted_at?: string | null;
  extraction_model?: string | null;
  latest_log_status?: string | null;
  latest_log_error?: string | null;
  confidence?: string | null;
  text_source?: string | null;
}

/**
 * Extrait les règles paie depuis le texte CC (super admin)
 */
export const extractRules = (agreementId: string, dryRun = false) => {
  return apiClient.post<ExtractRulesResponse>(
    `/api/collective-agreements/catalog/${agreementId}/extract-rules`,
    null,
    { params: { dry_run: dryRun } }
  );
};

/**
 * Extraction batch des règles paie (super admin)
 */
export const extractRulesBatch = (data: {
  idcc_list?: string[];
  all_catalog?: boolean;
  priority_only?: boolean;
  dry_run?: boolean;
}) => {
  return apiClient.post<ExtractRulesBatchResponse>(
    '/api/collective-agreements/catalog/extract-rules/batch',
    data
  );
};

/**
 * Statut des règles paie pour une convention (super admin)
 */
export const getRulesStatus = (agreementId: string) => {
  return apiClient.get<RulesStatusResponse>(
    `/api/collective-agreements/catalog/${agreementId}/rules-status`
  );
};

export interface CcTrainingRecommendation {
  id: string;
  idcc: string;
  agreement_id?: string | null;
  title: string;
  obligation_level: string;
  pedagogical_objective?: string | null;
  legal_reference?: string | null;
  target_roles: string[];
  periodicity?: string | null;
  is_active: boolean;
  source: string;
  confidence?: string | null;
  extracted_at?: string | null;
  extraction_model?: string | null;
}

export interface ExtractTrainingsResponse {
  success: boolean;
  idcc: string;
  agreement_id?: string | null;
  count: number;
  recommendations?: CcTrainingRecommendation[];
  error?: string | null;
  tokens_used: number;
}

export const extractTrainings = (agreementId: string, dryRun = false) => {
  return apiClient.post<ExtractTrainingsResponse>(
    `/api/collective-agreements/catalog/${agreementId}/extract-trainings`,
    null,
    { params: { dry_run: dryRun } }
  );
};

export const listTrainingRecommendations = (agreementId: string) => {
  return apiClient.get<CcTrainingRecommendation[]>(
    `/api/collective-agreements/catalog/${agreementId}/training-recommendations`
  );
};

export const patchTrainingRecommendation = (
  recommendationId: string,
  body: Partial<Pick<CcTrainingRecommendation, 'title' | 'is_active' | 'obligation_level' | 'pedagogical_objective' | 'legal_reference'>>
) => {
  return apiClient.patch<CcTrainingRecommendation>(
    `/api/collective-agreements/training-recommendations/${recommendationId}`,
    body
  );
};
