import apiClient from '@/api/apiClient';
import { openSignedUrlPreview, type SignedPdfPreviewOptions } from '@/lib/openSignedUrlPreview';

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
  docx_file_url?: string | null;
  docx_file_name?: string | null;
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
  /** Valeurs avant/après pour les avenants (snapshot ou diff fiche). */
  ancien_salaire?: number | null;
  ancien_poste?: string | null;
  nouveau_poste?: string | null;
  ancienne_duree?: string | null;
  nouvelle_duree?: string | null;
  ancien_lieu?: string | null;
  nouveau_lieu?: string | null;
  custom_fields?: Record<string, string> | null;
  recruitment_job_id?: string | null;
}

export interface ExplorerPayslipItem {
  id: string;
  employee_id: string;
  employee_name: string;
  name: string;
  url: string;
  preview_url?: string;
  month: number;
  year: number;
}

export interface ExplorerStorageItem {
  employee_id: string;
  employee_name: string;
  kind: 'contract' | 'identity' | 'credentials';
  url: string;
  preview_url?: string;
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

export async function transmitEmployeeDocument(
  employeeId: string,
  file: File,
  documentLabel: string,
  sendImmediately = true,
): Promise<GeneratedDocument> {
  const formData = new FormData();
  formData.append('employee_id', employeeId);
  formData.append('document_label', documentLabel.trim());
  formData.append('send_immediately', sendImmediately ? 'true' : 'false');
  formData.append('file', file, file.name || 'document.pdf');
  const response = await apiClient.post<GeneratedDocument>('/api/documents/transmit', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
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

export type DocumentFileFormat = 'pdf' | 'docx';

export async function downloadDocument(
  id: string,
  format: DocumentFileFormat = 'pdf'
): Promise<DocumentDownloadResult> {
  const response = await apiClient.get<DocumentDownloadResult>(`/api/documents/${id}/download`, {
    params: { format },
  });
  return response.data;
}

export async function previewDocument(id: string): Promise<DocumentDownloadResult> {
  const response = await apiClient.get<DocumentDownloadResult>(`/api/documents/${id}/preview`);
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
  const hasExtension = /\.[a-z0-9]+$/i.test(raw);
  const fallbackExt = /\.([a-z0-9]+)$/i.exec(fallbackFileName)?.[1] ?? 'pdf';
  const downloadName = hasExtension ? raw : `${raw}.${fallbackExt}`;

  const a = document.createElement('a');
  a.href = result.signed_url;
  a.download = downloadName;
  a.target = '_blank';
  a.rel = 'noopener noreferrer';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/** Ouvre le PDF dans le dialogue d’aperçu intégré. */
export async function openDocumentPreview(
  id: string,
  options?: SignedPdfPreviewOptions & { downloadName?: string }
): Promise<void> {
  const res = await previewDocument(id);
  openSignedUrlPreview(res.signed_url, {
    title: options?.title ?? 'Aperçu du document',
    subtitle: options?.subtitle,
    downloadName: options?.downloadName ?? res.file_name ?? 'document.pdf',
    downloadUrl: res.signed_url,
  });
}
