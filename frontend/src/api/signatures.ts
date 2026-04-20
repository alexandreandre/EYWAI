import apiClient from "@/api/apiClient";

export interface PendingSignatureItem {
  id: string;
  document_name: string;
  employee_id: string;
  employee_first_name?: string;
  employee_last_name?: string;
  yousign_procedure_id?: string;
  signature_status: string;
  sent_at?: string;
  expires_at?: string;
  days_until_expiry?: number;
  is_urgent: boolean;
  last_reminder_at?: string;
  days_since_reminder?: number;
  created_at: string;
}

export interface PendingSignaturesResponse {
  yousign_configured?: boolean;
  total: number;
  items: PendingSignatureItem[];
}

export async function getPendingSignaturesRH(): Promise<PendingSignaturesResponse> {
  const { data } = await apiClient.get<PendingSignaturesResponse>("/api/signatures/pending");
  return data;
}

export async function getPendingSignaturesME(): Promise<PendingSignaturesResponse> {
  const { data } = await apiClient.get<PendingSignaturesResponse>("/api/signatures/me/pending");
  return data;
}

export interface SendSignatureReminderResult {
  success: boolean;
  reminded_at?: string;
  error?: string;
}

export async function sendSignatureReminder(
  reviewId: string
): Promise<SendSignatureReminderResult> {
  const { data } = await apiClient.post<SendSignatureReminderResult>(
    `/api/signatures/${reviewId}/remind`
  );
  return data;
}
