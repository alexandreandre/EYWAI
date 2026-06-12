import apiClient from '@/api/apiClient';
import type {
  AccountingConfig,
  AccountingConfigUpdate,
  AccountingTransmission,
  TransmissionStatus,
} from '@/api/accountingIntegration';

export interface PlatformProviderEntry {
  provider_key: string;
  name: string;
  logo_key: string;
  enabled: boolean;
  has_platform_credentials: boolean;
  settings: Record<string, unknown>;
  last_test_at: string | null;
  last_test_status: string | null;
  last_test_message: string | null;
  description: string;
  connector_ready: boolean;
}

export interface PlatformCatalogResponse {
  providers: PlatformProviderEntry[];
  stats: Record<string, number>;
}

export interface PlatformProviderUpdate {
  enabled?: boolean;
  settings?: Record<string, unknown>;
  platform_credentials?: Record<string, string>;
}

export async function getPlatformAccountingCatalog(): Promise<PlatformCatalogResponse> {
  const { data } = await apiClient.get<PlatformCatalogResponse>(
    '/api/super-admin/accounting-integrations/catalog',
  );
  return data;
}

export async function updatePlatformAccountingProvider(
  providerKey: string,
  body: PlatformProviderUpdate,
): Promise<PlatformProviderEntry> {
  const { data } = await apiClient.put<PlatformProviderEntry>(
    `/api/super-admin/accounting-integrations/catalog/${providerKey}`,
    body,
  );
  return data;
}

export async function getAdminAccountingTransmissions(params?: {
  company_id?: string;
  period?: string;
  status?: TransmissionStatus;
  provider?: string;
  limit?: number;
}): Promise<{
  transmissions: AccountingTransmission[];
  total: number;
  counts_by_status: Record<string, number>;
}> {
  const { data } = await apiClient.get<{
    transmissions: AccountingTransmission[];
    total: number;
    counts_by_status: Record<string, number>;
  }>('/api/super-admin/accounting-integrations/transmissions', { params });
  return data;
}

export async function adminRetryAccountingTransmission(
  transmissionId: string,
  companyId: string,
): Promise<{ success: boolean; message: string }> {
  const { data } = await apiClient.post<{ success: boolean; message: string }>(
    `/api/super-admin/accounting-integrations/transmissions/${transmissionId}/retry`,
    {},
    { params: { company_id: companyId } },
  );
  return data;
}

export async function getAdminCompanyAccountingConfig(
  companyId: string,
): Promise<AccountingConfig> {
  const { data } = await apiClient.get<AccountingConfig>(
    `/api/super-admin/accounting-integrations/companies/${companyId}/config`,
  );
  return data;
}

export async function adminUpdateCompanyAccountingConfig(
  companyId: string,
  body: AccountingConfigUpdate,
): Promise<AccountingConfig> {
  const { data } = await apiClient.patch<AccountingConfig>(
    `/api/super-admin/accounting-integrations/companies/${companyId}/config`,
    body,
  );
  return data;
}

export async function adminTestCompanyAccountingConnection(
  companyId: string,
): Promise<{ success: boolean; status: string; message: string }> {
  const { data } = await apiClient.post<{ success: boolean; status: string; message: string }>(
    `/api/super-admin/accounting-integrations/companies/${companyId}/test-connection`,
    {},
  );
  return data;
}
