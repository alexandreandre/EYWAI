import apiClient from '@/api/apiClient';

export const DOCUMENT_TYPE_LABELS: Record<string, string> = {
  cdi: 'CDI',
  cdd: 'CDD',
  convention_stage: 'Convention de stage',
  contrat_alternance: "Contrat d'alternance",
  avenant_salaire: 'Avenant - Modification de salaire',
  avenant_poste: 'Avenant - Changement de poste',
  avenant_temps: 'Avenant - Modification du temps de travail',
  avenant_lieu: 'Avenant - Changement de lieu de travail',
  avenant_general: 'Avenant - Modification générale',
  attestation_emploi: "Attestation d'emploi",
  attestation_presence: 'Attestation de présence',
  attestation_anciennete: "Attestation d'ancienneté",
  attestation_poste: 'Attestation de poste',
  attestation_salaire: 'Attestation de salaire',
  attestation_revenus: 'Attestation de revenus annuels',
  attestation_location: 'Attestation employeur pour location',
  attestation_pret: 'Attestation pour prêt bancaire',
  attestation_retraite: 'Attestation retraite',
};

export interface DocumentTemplateVersion {
  id: string;
  template_id: string;
  version: number;
  file_url: string;
  file_name: string;
  file_format: string;
  file_size: number | null;
  uploaded_by: string | null;
  created_at: string;
}

export interface DocumentTemplate {
  id: string;
  company_id: string;
  document_type: string;
  name: string;
  is_default: boolean;
  status: string;
  created_at: string;
  updated_at: string;
  current_version: DocumentTemplateVersion | null;
  versions_count: number;
}

export interface DocumentTemplateCreate {
  document_type: string;
  name?: string | null;
}

export interface DocumentTemplateUpdate {
  name?: string | null;
  is_default?: boolean | null;
  status?: 'active' | 'archived' | null;
}

export async function getTemplates(status?: string): Promise<DocumentTemplate[]> {
  const response = await apiClient.get<DocumentTemplate[]>('/api/document-library/', {
    params: status ? { status } : undefined,
  });
  return response.data;
}

export async function getTemplate(id: string): Promise<DocumentTemplate> {
  const response = await apiClient.get<DocumentTemplate>(`/api/document-library/${id}`);
  return response.data;
}

export async function getMissingTypes(): Promise<string[]> {
  const response = await apiClient.get<string[]>('/api/document-library/missing-types');
  return response.data;
}

export async function createTemplate(data: DocumentTemplateCreate): Promise<DocumentTemplate> {
  const response = await apiClient.post<DocumentTemplate>('/api/document-library/', data);
  return response.data;
}

export async function updateTemplate(
  id: string,
  data: DocumentTemplateUpdate
): Promise<DocumentTemplate> {
  const response = await apiClient.put<DocumentTemplate>(`/api/document-library/${id}`, data);
  return response.data;
}

export async function archiveTemplate(id: string): Promise<DocumentTemplate> {
  const response = await apiClient.post<DocumentTemplate>(`/api/document-library/${id}/archive`);
  return response.data;
}

export async function getVersions(id: string): Promise<DocumentTemplateVersion[]> {
  const response = await apiClient.get<DocumentTemplateVersion[]>(
    `/api/document-library/${id}/versions`
  );
  return response.data;
}

export async function uploadTemplateFile(id: string, file: File): Promise<DocumentTemplateVersion> {
  const form = new FormData();
  form.append('file', file);
  const response = await apiClient.post<DocumentTemplateVersion>(
    `/api/document-library/${id}/upload`,
    form
  );
  return response.data;
}

export async function getVersionDownloadUrl(
  templateId: string,
  versionId: string
): Promise<string> {
  const response = await apiClient.get<{ signed_url: string }>(
    `/api/document-library/${templateId}/versions/${versionId}/download-url`
  );
  return response.data.signed_url;
}

export async function restoreTemplateVersion(
  templateId: string,
  versionId: string
): Promise<DocumentTemplateVersion> {
  const response = await apiClient.post<DocumentTemplateVersion>(
    `/api/document-library/${templateId}/versions/${versionId}/restore`
  );
  return response.data;
}
