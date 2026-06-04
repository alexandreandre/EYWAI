// frontend/src/api/netEntreprises.ts
// API Net-entreprises : configuration de connexion + suivi des télétransmissions DSN.

import apiClient from '@/api/apiClient';

export type TransmissionMode = 'manual' | 'api_certificat' | 'api_declarant';

export type TransmissionStatus =
  | 'generated'
  | 'manual'
  | 'queued'
  | 'sent'
  | 'acknowledged'
  | 'rejected';

export type ConnectionState = 'not_configured' | 'manual' | 'connected';

export interface NetEntreprisesConfig {
  enabled: boolean;
  mode: TransmissionMode;
  siret_declarant: string | null;
  raison_sociale_declarant: string | null;
  identifiant: string | null;
  contact_email: string | null;
  certificat_label: string | null;
  certificat_expires_at: string | null;
  has_secret: boolean;
  last_test_at: string | null;
  last_test_status: string | null;
  last_test_message: string | null;
  connection_state: ConnectionState;
}

export interface NetEntreprisesConfigUpdate {
  enabled?: boolean;
  mode?: TransmissionMode;
  siret_declarant?: string | null;
  raison_sociale_declarant?: string | null;
  identifiant?: string | null;
  contact_email?: string | null;
  certificat_label?: string | null;
  certificat_expires_at?: string | null;
  secret?: string | null;
}

export interface ConnectionTestResult {
  success: boolean;
  status: string;
  message: string;
}

export interface DSNTransmission {
  id: string;
  period: string;
  dsn_type: string;
  status: TransmissionStatus;
  mode: TransmissionMode;
  net_entreprises_ref: string | null;
  submitted_at: string | null;
  acknowledged_at: string | null;
  error_message: string | null;
  crm_retour: Record<string, unknown> | null;
  created_at: string | null;
}

export interface DSNTransmissionsResponse {
  transmissions: DSNTransmission[];
}

export interface AdminDSNTransmission extends DSNTransmission {
  company_id: string;
  company_name: string | null;
}

export interface AdminDSNTransmissionsResponse {
  transmissions: AdminDSNTransmission[];
  counts_by_status: Record<string, number>;
}

// --- Config (RH) ---

export async function getNetEntreprisesConfig(): Promise<NetEntreprisesConfig> {
  const res = await apiClient.get<NetEntreprisesConfig>('/api/net-entreprises/config');
  return res.data;
}

export async function updateNetEntreprisesConfig(
  data: NetEntreprisesConfigUpdate,
): Promise<NetEntreprisesConfig> {
  const res = await apiClient.put<NetEntreprisesConfig>('/api/net-entreprises/config', data);
  return res.data;
}

export async function testNetEntreprisesConnection(): Promise<ConnectionTestResult> {
  const res = await apiClient.post<ConnectionTestResult>(
    '/api/net-entreprises/config/test-connection',
  );
  return res.data;
}

// --- Suivi (RH) ---

export async function getNetEntreprisesTransmissions(
  period?: string,
): Promise<DSNTransmissionsResponse> {
  const res = await apiClient.get<DSNTransmissionsResponse>(
    '/api/net-entreprises/transmissions',
    { params: period ? { period } : undefined },
  );
  return res.data;
}

export async function markTransmissionTransmitted(
  transmissionId: string,
  netEntreprisesRef?: string,
): Promise<DSNTransmission> {
  const res = await apiClient.post<DSNTransmission>(
    `/api/net-entreprises/transmissions/${transmissionId}/mark-transmitted`,
    { net_entreprises_ref: netEntreprisesRef ?? null },
  );
  return res.data;
}

// --- Suivi & pilotage plateforme (super-admin) ---

export async function getAdminNetEntreprisesTransmissions(params?: {
  status?: string;
  period?: string;
}): Promise<AdminDSNTransmissionsResponse> {
  const res = await apiClient.get<AdminDSNTransmissionsResponse>(
    '/api/super-admin/net-entreprises/transmissions',
    {
      params: {
        ...(params?.status ? { status_filter: params.status } : {}),
        ...(params?.period ? { period: params.period } : {}),
      },
    },
  );
  return res.data;
}

export async function getAdminNetEntreprisesConfig(
  companyId: string,
): Promise<NetEntreprisesConfig> {
  const res = await apiClient.get<NetEntreprisesConfig>(
    `/api/super-admin/net-entreprises/config/${companyId}`,
  );
  return res.data;
}

export async function updateAdminNetEntreprisesConfig(
  companyId: string,
  data: NetEntreprisesConfigUpdate,
): Promise<NetEntreprisesConfig> {
  const res = await apiClient.put<NetEntreprisesConfig>(
    `/api/super-admin/net-entreprises/config/${companyId}`,
    data,
  );
  return res.data;
}

// --- Helpers d'affichage ---

export const TRANSMISSION_STATUS_LABELS: Record<TransmissionStatus, string> = {
  generated: 'Généré',
  manual: 'À déposer (manuel)',
  queued: "En file d'envoi",
  sent: 'Envoyé',
  acknowledged: 'Accusé reçu',
  rejected: 'Rejeté',
};

export const TRANSMISSION_MODE_LABELS: Record<TransmissionMode, string> = {
  manual: 'Manuel',
  api_certificat: 'API (certificat)',
  api_declarant: 'API (déclarant)',
};
