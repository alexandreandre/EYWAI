import apiClient from "@/api/apiClient";

export interface TurnoverStats {
  taux_turnover_annuel: number;
  nb_departs_12_mois: number;
  nb_embauches_12_mois: number;
  taux_embauches: number;
  taux_departs: number;
}

export interface PyramideAge {
  tranche: string;
  count: number;
  pourcentage: number;
}

export interface AbsentéismeDetail {
  taux_global: number;
  taux_maladie: number;
  taux_at: number;
  taux_autres: number;
  jours_perdus_total: number;
  jours_perdus_maladie: number;
  jours_perdus_at: number;
  jours_perdus_autres: number;
  evolution_vs_mois_precedent: number;
}

export interface AnalyticsAvances {
  turnover: TurnoverStats;
  pyramide_ages: PyramideAge[];
  absenteisme: AbsentéismeDetail;
  effectif_par_service: Array<Record<string, unknown>>;
  effectif_par_contrat: Array<Record<string, unknown>>;
  masse_salariale_par_service: Array<Record<string, unknown>>;
}

export async function getAnalyticsAvances(
  companyId?: string | null,
): Promise<AnalyticsAvances> {
  const headers =
    companyId && companyId.length > 0
      ? { "X-Active-Company": companyId }
      : undefined;
  const { data } = await apiClient.get<AnalyticsAvances>(
    "/api/dashboard/analytics",
    { headers },
  );
  return data;
}

export type SeveriteAnomalie = "bloquant" | "avertissement";

export interface AnomaliePayslip {
  employee_id: string;
  employee_name: string;
  payslip_id: string;
  type: string;
  severite: SeveriteAnomalie;
  message: string;
  valeur_detectee: string;
  suggestion_correction: string;
}

export interface AnomaliesReport {
  year: number;
  month: number;
  total_bulletins: number;
  bulletins_avec_anomalies: number;
  anomalies: AnomaliePayslip[];
}

export interface AuditLogEntry {
  id: string;
  company_id: string;
  user_id: string | null;
  user_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown> | null;
  ip_address: string | null;
  created_at: string;
}

export const ACTIONS_LABELS: Record<string, string> = {
  "employee.create": "Création salarié",
  "employee.update": "Modification salarié",
  "employee.delete": "Suppression salarié",
  "payslip.validate": "Validation bulletin",
  "payslip.generate": "Génération bulletin",
  "absence.validate": "Validation absence",
  "absence.reject": "Refus absence",
  "document.sign": "Signature document",
  "salary.update": "Modification salaire",
  "recruitment.hire": "Embauche candidat",
};

export async function getAnomaliesPayslips(
  companyId: string | null | undefined,
  year?: number,
  month?: number,
): Promise<AnomaliesReport> {
  const headers =
    companyId && companyId.length > 0
      ? { "X-Active-Company": companyId }
      : undefined;
  const { data } = await apiClient.get<AnomaliesReport>("/api/payslips/anomalies", {
    headers,
    params: {
      ...(year != null ? { year } : {}),
      ...(month != null ? { month } : {}),
    },
  });
  return data;
}

export type GetAuditLogsParams = {
  resource_type?: string;
  resource_id?: string;
  user_id?: string;
  created_after?: string;
  created_before?: string;
  limit?: number;
  offset?: number;
};

export async function getAuditLogs(
  companyId: string | null | undefined,
  params?: GetAuditLogsParams,
): Promise<AuditLogEntry[]> {
  const headers =
    companyId && companyId.length > 0
      ? { "X-Active-Company": companyId }
      : undefined;
  const { data } = await apiClient.get<AuditLogEntry[]>("/api/audit/logs", {
    headers,
    params: {
      resource_type: params?.resource_type,
      resource_id: params?.resource_id,
      user_id: params?.user_id,
      created_after: params?.created_after,
      created_before: params?.created_before,
      limit: params?.limit ?? 50,
      offset: params?.offset ?? 0,
    },
  });
  return data;
}

// --- Webhooks (intégrations / BI) ---

export const WEBHOOK_EVENTS: string[] = [
  "employee.hired",
  "employee.left",
  "employee.salary_updated",
  "payslip.validated",
  "absence.approved",
  "document.signed",
  "recruitment.hired",
];

export interface WebhookConfig {
  id: string;
  company_id: string;
  name: string;
  url: string;
  events: string[];
  is_active: boolean;
  last_triggered_at: string | null;
  last_status_code: number | null;
  created_at: string;
}

export interface WebhookLog {
  id: string;
  webhook_id: string;
  event_type: string;
  response_status: number | null;
  duration_ms: number | null;
  created_at: string;
}

export type WebhookCreatePayload = {
  name: string;
  url: string;
  secret?: string | null;
  events: string[];
};

export type WebhookUpdatePayload = {
  name?: string;
  url?: string;
  secret?: string | null;
  events?: string[];
  is_active?: boolean;
};

function webhookHeaders(companyId: string | null | undefined) {
  if (!companyId) {
    throw new Error("companyId requis");
  }
  return { "X-Active-Company": companyId };
}

export async function getWebhooks(
  companyId: string | null | undefined,
): Promise<WebhookConfig[]> {
  const { data } = await apiClient.get<WebhookConfig[]>("/api/webhooks", {
    headers: webhookHeaders(companyId),
  });
  return data;
}

export async function createWebhook(
  companyId: string | null | undefined,
  body: WebhookCreatePayload,
): Promise<WebhookConfig> {
  const { data } = await apiClient.post<WebhookConfig>("/api/webhooks", body, {
    headers: webhookHeaders(companyId),
  });
  return data;
}

export async function updateWebhook(
  id: string,
  companyId: string | null | undefined,
  body: WebhookUpdatePayload,
): Promise<WebhookConfig> {
  const { data } = await apiClient.patch<WebhookConfig>(
    `/api/webhooks/${id}`,
    body,
    { headers: webhookHeaders(companyId) },
  );
  return data;
}

export async function deleteWebhook(
  id: string,
  companyId: string | null | undefined,
): Promise<void> {
  await apiClient.delete(`/api/webhooks/${id}`, {
    headers: webhookHeaders(companyId),
  });
}

export async function testWebhook(
  id: string,
  companyId: string | null | undefined,
): Promise<{ status_code: number; success: boolean }> {
  const { data } = await apiClient.post<{ status_code: number; success: boolean }>(
    `/api/webhooks/${id}/test`,
    {},
    { headers: webhookHeaders(companyId) },
  );
  return data;
}

export async function getWebhookLogs(
  id: string,
  companyId: string | null | undefined,
): Promise<WebhookLog[]> {
  const { data } = await apiClient.get<WebhookLog[]>(
    `/api/webhooks/${id}/logs`,
    { headers: webhookHeaders(companyId) },
  );
  return data;
}
