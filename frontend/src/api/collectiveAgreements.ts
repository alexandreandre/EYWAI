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

/**
 * Récupère la grille de classification pour une convention collective
 */
export const getClassifications = (agreementId: string) => {
  return apiClient.get<ClassificationConventionnelle[]>(`/api/collective-agreements/catalog/${agreementId}/classifications`);
};

// =====================================================================
// API - ASSIGNATION (RH/Admin)
// =====================================================================

/**
 * Récupère toutes les conventions assignées à l'entreprise
 */
export const getMyCompanyAgreements = () => {
  return apiClient.get<CompanyCollectiveAgreementWithDetails[]>('/api/collective-agreements/my-company');
};

/**
 * Assigne une convention à l'entreprise
 */
export const assignAgreement = (collectiveAgreementId: string) => {
  return apiClient.post('/api/collective-agreements/assign', {
    collective_agreement_id: collectiveAgreementId
  });
};

/**
 * Retire une convention de l'entreprise
 */
export const unassignAgreement = (assignmentId: string) => {
  return apiClient.delete(`/api/collective-agreements/unassign/${assignmentId}`);
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
export const importFromLegifrance = (data: {
  idcc: string;
  extract_rules?: boolean;
  sector?: string;
}) => {
  return apiClient.post<KaliImportResponse>(
    '/api/collective-agreements/catalog/import-legifrance',
    data
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
 * Ré-import Légifrance pour une fiche existante
 */
export const reimportFromLegifrance = (agreementId: string, extractRules = true) => {
  return apiClient.post<KaliImportResponse>(
    `/api/collective-agreements/catalog/${agreementId}/import-legifrance`,
    null,
    { params: { extract_rules: extractRules } }
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
