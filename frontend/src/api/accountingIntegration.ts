import apiClient from '@/api/apiClient';

export type AccountingMode =
  | 'manual'
  | 'api_quadra'
  | 'api_sage'
  | 'api_pennylane'
  | 'sftp';

export type AccountingConnectionState =
  | 'not_configured'
  | 'manual'
  | 'connected'
  | 'stub'
  | 'failed';

export type TransmissionStatus =
  | 'generated'
  | 'queued'
  | 'sent'
  | 'transmitted'
  | 'acknowledged'
  | 'rejected'
  | 'manual'
  | 'failed';

export type CegidAuthMode = 'shared' | 'dedicated';
export type CegidAuthSource = 'shared' | 'dedicated' | 'incomplete';

export interface AccountingConfig {
  enabled: boolean;
  mode: AccountingMode;
  provider: string;
  default_format: string;
  recipients_compta: string[];
  has_credentials: boolean;
  cegid_credentials_complete: boolean;
  has_platform_cegid_credentials: boolean;
  code_dossier_cegid: string | null;
  cegid_auth_mode: CegidAuthMode;
  cegid_auth_source: CegidAuthSource;
  force_manual: boolean;
  last_transmission_at: string | null;
  last_test_at: string | null;
  last_test_status: string | null;
  last_test_message: string | null;
  connection_state: AccountingConnectionState;
}

export interface AccountingConfigUpdate {
  enabled?: boolean;
  mode?: AccountingMode;
  provider?: string;
  default_format?: string;
  recipients_compta?: string[];
  credentials?: Record<string, string>;
  code_dossier_cegid?: string;
  cegid_auth_mode?: CegidAuthMode;
  clear_company_credentials?: boolean;
  force_manual?: boolean;
}

export interface AccountingConnectionTest {
  success: boolean;
  status: string;
  message: string;
}

export interface ProviderDefinition {
  key: string;
  name: string;
  logo_key: string;
  mode: string;
  capabilities: string[];
  auth_type: string;
  supported_formats: string[];
  doc_url: string;
  description: string;
  platform_enabled: boolean;
  connector_ready: boolean;
}

export interface AccountingTransmission {
  id: string;
  company_id: string;
  company_name?: string | null;
  period: string;
  channel: string;
  provider: string;
  mode: string;
  status: TransmissionStatus;
  export_ids: string[];
  external_ref?: string | null;
  error_message?: string | null;
  created_at?: string | null;
  submitted_at?: string | null;
  acknowledged_at?: string | null;
}

export interface TransmitComptaResult {
  success: boolean;
  status: string;
  message: string;
  transmission_id?: string | null;
  external_ref?: string | null;
  manual_fallback: boolean;
}

function companyHeaders(companyId: string | null | undefined) {
  return companyId ? { 'X-Active-Company': companyId } : {};
}

export async function getAccountingConfig(
  companyId: string | null | undefined,
): Promise<AccountingConfig> {
  const { data } = await apiClient.get<AccountingConfig>(
    '/api/accounting-integration/config',
    { headers: companyHeaders(companyId) },
  );
  return data;
}

export async function updateAccountingConfig(
  companyId: string | null | undefined,
  body: AccountingConfigUpdate,
): Promise<AccountingConfig> {
  const { data } = await apiClient.patch<AccountingConfig>(
    '/api/accounting-integration/config',
    body,
    { headers: companyHeaders(companyId) },
  );
  return data;
}

export async function testAccountingConnection(
  companyId: string | null | undefined,
): Promise<AccountingConnectionTest> {
  const { data } = await apiClient.post<AccountingConnectionTest>(
    '/api/accounting-integration/test-connection',
    {},
    { headers: companyHeaders(companyId) },
  );
  return data;
}

export async function getAccountingProviders(
  companyId: string | null | undefined,
): Promise<ProviderDefinition[]> {
  const { data } = await apiClient.get<{ providers: ProviderDefinition[] }>(
    '/api/accounting-integration/providers',
    { headers: companyHeaders(companyId) },
  );
  return data.providers;
}

export async function getAccountingTransmissions(
  companyId: string | null | undefined,
  params?: { period?: string; status?: string; limit?: number },
): Promise<{ transmissions: AccountingTransmission[]; total: number; counts_by_status: Record<string, number> }> {
  const { data } = await apiClient.get<{
    transmissions: AccountingTransmission[];
    total: number;
    counts_by_status: Record<string, number>;
  }>('/api/accounting-integration/transmissions', {
    headers: companyHeaders(companyId),
    params,
  });
  return data;
}

export async function retryAccountingTransmission(
  companyId: string | null | undefined,
  transmissionId: string,
): Promise<TransmitComptaResult> {
  const { data } = await apiClient.post<TransmitComptaResult>(
    `/api/accounting-integration/transmissions/${transmissionId}/retry`,
    {},
    { headers: companyHeaders(companyId) },
  );
  return data;
}

export const TRANSMISSION_STATUS_LABELS: Record<TransmissionStatus, string> = {
  generated: 'Généré',
  queued: 'En file',
  sent: 'Soumis',
  transmitted: 'Intégré',
  acknowledged: 'Accusé',
  rejected: 'Rejeté',
  manual: 'Manuel',
  failed: 'Échec',
};
