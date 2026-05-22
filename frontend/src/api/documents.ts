import apiClient from '@/api/apiClient';

export type DocumentStatus = 'brouillon' | 'envoye' | 'signe' | 'archive';

export type DocumentCategory =
  | 'contrat'
  | 'avenant'
  | 'attestation_sortie'
  | 'attestation_situation'
  | 'attestation_courante';

export interface GeneratedDocument {
  id: string;
  company_id: string;
  employee_id: string | null;
  document_type: string;
  category: string;
  template_id: string | null;
  template_version_id: string | null;
  is_eywai_template: boolean;
  file_url: string | null;
  file_name: string | null;
  status: string;
  generation_context: Record<string, unknown>;
  generated_by: string | null;
  created_at: string;
  updated_at: string;
  employee_name?: string | null;
  template_name?: string | null;
}

export interface DocumentsFilters {
  employee_id?: string;
  document_type?: string;
  status?: DocumentStatus;
  date_from?: string;
  date_to?: string;
}

export interface GenerateDocumentPayload {
  employee_id: string;
  document_type: string;
  category: DocumentCategory;
  date_effet?: string | null;
  motif?: string | null;
  template_id?: string | null;
  /** Persisté côté serveur dans generation_context (rebouclage à la signature). */
  nouveau_salaire?: number | null;
}

export interface ExplorerPayslipItem {
  id: string;
  employee_id: string;
  employee_name: string;
  name: string;
  url: string;
  month: number;
  year: number;
}

export interface ExplorerStorageItem {
  employee_id: string;
  employee_name: string;
  kind: 'contract' | 'identity' | 'credentials';
  url: string;
  label: string;
}

export interface DocumentsExplorerResponse {
  generated: GeneratedDocument[];
  payslips: ExplorerPayslipItem[];
  storage: ExplorerStorageItem[];
}

export async function getDocumentsExplorer(): Promise<DocumentsExplorerResponse> {
  const response = await apiClient.get<DocumentsExplorerResponse>('/api/documents/explorer');
  return response.data;
}

export async function getDocuments(filters?: DocumentsFilters): Promise<GeneratedDocument[]> {
  const raw = filters ?? {};
  const params = Object.fromEntries(
    Object.entries(raw).filter(([, v]) => v !== undefined && v !== null && v !== '')
  );
  const response = await apiClient.get<GeneratedDocument[]>('/api/documents/', {
    params: Object.keys(params).length ? params : undefined,
  });
  return response.data;
}

export async function getDocument(id: string): Promise<GeneratedDocument> {
  const response = await apiClient.get<GeneratedDocument>(`/api/documents/${id}`);
  return response.data;
}

export async function generateDocument(data: GenerateDocumentPayload): Promise<GeneratedDocument> {
  const response = await apiClient.post<GeneratedDocument>('/api/documents/generate', data);
  return response.data;
}

export async function updateDocumentStatus(
  id: string,
  status: DocumentStatus
): Promise<GeneratedDocument> {
  const response = await apiClient.put<GeneratedDocument>(`/api/documents/${id}/status`, {
    status,
  });
  return response.data;
}

export async function deleteDocument(id: string): Promise<void> {
  await apiClient.delete(`/api/documents/${id}`);
}

/** Réponse GET /api/documents/{id}/download (file_name optionnel si l’API l’ajoute plus tard). */
export type DocumentDownloadResult = {
  signed_url: string;
  file_name?: string | null;
};

export async function downloadDocument(id: string): Promise<DocumentDownloadResult> {
  const response = await apiClient.get<DocumentDownloadResult>(`/api/documents/${id}/download`);
  return response.data;
}

/**
 * Déclenche le téléchargement / ouverture du PDF à partir de l’URL signée (évite window.open seul).
 */
export function triggerSignedDocumentDownload(
  result: DocumentDownloadResult,
  fallbackFileName = 'document.pdf'
): void {
  const raw = (result.file_name && result.file_name.trim()) || fallbackFileName.trim() || 'document.pdf';
  const downloadName = raw.toLowerCase().endsWith('.pdf') ? raw : `${raw}.pdf`;

  const a = document.createElement('a');
  a.href = result.signed_url;
  a.download = downloadName;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/** Ouvre le PDF dans un nouvel onglet (aperçu navigateur). */
export async function openDocumentPreview(id: string): Promise<void> {
  const res = await downloadDocument(id);
  window.open(res.signed_url, '_blank', 'noopener,noreferrer');
}
