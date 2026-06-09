import apiClient from './apiClient';
import type {
  BadgeuseDashboardToday,
  PunchCandidate,
  ScanPunchResult,
} from './badgeuse';

export interface BadgeuseTerminalStatus {
  device_id: string;
  company_id: string;
  company_name?: string | null;
  logo_url?: string | null;
  label: string;
  ok: boolean;
}

export interface BadgeuseTerminalDevice {
  id: string;
  company_id: string;
  label: string;
  token_prefix: string;
  created_by: string;
  last_used_at?: string | null;
  revoked_at?: string | null;
  created_at?: string;
  is_active: boolean;
}

export interface CreateTerminalDeviceResponse {
  device: BadgeuseTerminalDevice;
  token: string;
}

export const getTerminalStatus = async (): Promise<BadgeuseTerminalStatus> => {
  const response = await apiClient.get('/api/badgeuse/terminal/status');
  return response.data;
};

export const getTerminalDashboardToday = async (): Promise<BadgeuseDashboardToday> => {
  const response = await apiClient.get('/api/badgeuse/terminal/dashboard/today');
  return response.data;
};

export const getTerminalPunchCandidates = async (
  options?: { q?: string; onlyNotBadged?: boolean; limit?: number }
): Promise<PunchCandidate[]> => {
  const params = new URLSearchParams();
  if (options?.q?.trim()) params.set('q', options.q.trim());
  if (options?.onlyNotBadged) params.set('only_not_badged', 'true');
  if (options?.limit != null) params.set('limit', String(options.limit));
  const qs = params.toString();
  const response = await apiClient.get(
    `/api/badgeuse/terminal/punch-candidates${qs ? `?${qs}` : ''}`
  );
  return response.data ?? [];
};

export const scanBadgeQrTerminal = async (
  payload: { qr_payload?: string; employee_id?: string; username?: string }
): Promise<ScanPunchResult> => {
  const response = await apiClient.post('/api/badgeuse/terminal/scan', payload);
  return response.data;
};

export const listTerminalDevices = async (
  companyId: string
): Promise<BadgeuseTerminalDevice[]> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.get(
    `/api/badgeuse/terminal-devices?${params.toString()}`
  );
  return response.data ?? [];
};

export const activateTerminalDeviceHere = async (
  companyId: string,
  label?: string
): Promise<CreateTerminalDeviceResponse> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.post(
    `/api/badgeuse/terminal-devices/activate-here?${params.toString()}`,
    label ? { label } : {}
  );
  return response.data;
};

export const createTerminalDevice = async (
  companyId: string,
  label: string
): Promise<CreateTerminalDeviceResponse> => {
  const params = new URLSearchParams({ company_id: companyId });
  const response = await apiClient.post(
    `/api/badgeuse/terminal-devices?${params.toString()}`,
    { label }
  );
  return response.data;
};

export const revokeTerminalDevice = async (
  companyId: string,
  deviceId: string
): Promise<void> => {
  const params = new URLSearchParams({ company_id: companyId });
  await apiClient.delete(
    `/api/badgeuse/terminal-devices/${deviceId}?${params.toString()}`
  );
};
