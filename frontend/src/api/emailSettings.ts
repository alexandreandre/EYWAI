import apiClient from '@/api/apiClient';

export type SmtpSecurity = 'starttls' | 'ssl' | 'none';
export type EmailConfigSource = 'database' | 'environment' | 'none';

export interface EmailSettings {
  smtp_host: string | null;
  smtp_port: number;
  smtp_user: string | null;
  has_smtp_password: boolean;
  smtp_security: SmtpSecurity;
  from_email: string | null;
  from_name: string;
  reply_to: string | null;
  support_recipients: string[];
  is_active: boolean;
  is_configured: boolean;
  effective_source: EmailConfigSource;
  updated_at: string | null;
}

export interface EmailSettingsUpdate {
  smtp_host?: string | null;
  smtp_port?: number;
  smtp_user?: string | null;
  smtp_password?: string;
  smtp_security?: SmtpSecurity;
  from_email?: string | null;
  from_name?: string;
  reply_to?: string | null;
  support_recipients?: string[];
  is_active?: boolean;
}

export interface EmailTestRequest {
  to_email: string;
}

export interface EmailTestResponse {
  success: boolean;
  message: string;
}

export async function getEmailSettings(): Promise<EmailSettings> {
  const { data } = await apiClient.get<EmailSettings>('/api/super-admin/email-settings');
  return data;
}

export async function updateEmailSettings(
  payload: EmailSettingsUpdate,
): Promise<EmailSettings> {
  const { data } = await apiClient.put<EmailSettings>(
    '/api/super-admin/email-settings',
    payload,
  );
  return data;
}

export async function sendTestEmail(body: EmailTestRequest): Promise<EmailTestResponse> {
  const { data } = await apiClient.post<EmailTestResponse>(
    '/api/super-admin/email-settings/test',
    body,
  );
  return data;
}
