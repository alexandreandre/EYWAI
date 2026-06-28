import apiClient from '@/api/apiClient';

export type ParticipationChoiceType = 'full_cash' | 'partial_cash' | 'full_pee';

export interface CampaignStats {
  total: number;
  pending: number;
  sent: number;
  responded: number;
  default_pee: number;
  cancelled: number;
}

export interface ParticipationCampaign {
  id: string;
  company_id?: string;
  simulation_id?: string | null;
  year: number;
  exercise_label: string;
  status: 'draft' | 'open' | 'closed';
  payroll_year?: number | null;
  payroll_month?: number | null;
  sent_at?: string | null;
  deadline_at?: string | null;
  created_at: string;
  updated_at?: string;
  stats: CampaignStats;
}

export interface ParticipationBulletin {
  id: string;
  campaign_id: string;
  employee_id: string;
  employee_first_name?: string | null;
  employee_last_name?: string | null;
  dispositif_type: 'participation' | 'interessement';
  gross_amount: number;
  csg_non_deductible: number;
  csg_deductible: number;
  advance_amount: number;
  advance_label: string;
  net_amount: number;
  generated_document_id?: string | null;
  status: string;
  choice_type?: ParticipationChoiceType | null;
  choice_cash_amount?: number | null;
  pee_amount?: number | null;
  cash_amount?: number | null;
  responded_at?: string | null;
  deadline_at?: string | null;
  exercise_label?: string | null;
  year?: number | null;
}

export interface CampaignAdvanceInput {
  employee_id: string;
  amount: number;
  label: string;
}

export interface CampaignAmountInput {
  employee_id: string;
  participation_amount: number;
  interessement_amount: number;
}

export async function listCampaigns(year?: number): Promise<ParticipationCampaign[]> {
  const { data } = await apiClient.get<{ campaigns: ParticipationCampaign[] }>(
    '/api/participation/campaigns',
    { params: year != null ? { year } : undefined },
  );
  return data.campaigns ?? [];
}

export async function getCampaign(campaignId: string): Promise<ParticipationCampaign> {
  const { data } = await apiClient.get<ParticipationCampaign>(
    `/api/participation/campaigns/${campaignId}`,
  );
  return data;
}

export async function createCampaign(payload: {
  simulation_id?: string;
  year: number;
  exercise_label?: string;
  payroll_year?: number;
  payroll_month?: number;
  advances: CampaignAdvanceInput[];
  amounts: CampaignAmountInput[];
}): Promise<{ campaign: ParticipationCampaign; bulletins_created: number }> {
  const { data } = await apiClient.post<{
    campaign: ParticipationCampaign;
    bulletins_created: number;
  }>('/api/participation/campaigns', payload);
  return data;
}

export async function listCampaignBulletins(
  campaignId: string,
): Promise<ParticipationBulletin[]> {
  const { data } = await apiClient.get<{ bulletins: ParticipationBulletin[] }>(
    `/api/participation/campaigns/${campaignId}/bulletins`,
  );
  return data.bulletins ?? [];
}

export async function publishCampaign(
  campaignId: string,
): Promise<ParticipationCampaign> {
  const { data } = await apiClient.post<{ campaign: ParticipationCampaign }>(
    `/api/participation/campaigns/${campaignId}/publish`,
  );
  return data.campaign;
}

export async function remindCampaign(campaignId: string): Promise<ParticipationCampaign> {
  const { data } = await apiClient.post<{ campaign: ParticipationCampaign }>(
    `/api/participation/campaigns/${campaignId}/remind`,
  );
  return data.campaign;
}

export async function closeCampaignDefaults(
  campaignId: string,
): Promise<ParticipationCampaign> {
  const { data } = await apiClient.post<{ campaign: ParticipationCampaign }>(
    `/api/participation/campaigns/${campaignId}/close-defaults`,
  );
  return data.campaign;
}

export async function generateCampaignPayrollLines(
  campaignId: string,
  payroll_year: number,
  payroll_month: number,
): Promise<ParticipationCampaign> {
  const { data } = await apiClient.post<{ campaign: ParticipationCampaign }>(
    `/api/participation/campaigns/${campaignId}/generate-payroll-lines`,
    { payroll_year, payroll_month },
  );
  return data.campaign;
}

export interface RegularisationPayslipResult {
  detail: string;
  payslip_id?: string | null;
  download_url: string;
  year: number;
  month: number;
  employee_id: string;
}

/**
 * Génère un bulletin de paie de régularisation participation pour un bénéficiaire,
 * y compris un salarié déjà sorti (versement de la participation l'année suivante).
 */
export async function generateRegularisationPayslip(
  bulletinId: string,
): Promise<RegularisationPayslipResult> {
  const { data } = await apiClient.post<RegularisationPayslipResult>(
    `/api/participation/bulletins/${bulletinId}/regularisation-payslip`,
  );
  return data;
}

export async function listMyParticipationBulletins(): Promise<ParticipationBulletin[]> {
  const { data } = await apiClient.get<{ bulletins: ParticipationBulletin[] }>(
    '/api/participation/me/participation-bulletins',
  );
  return data.bulletins ?? [];
}

export async function respondParticipationBulletin(
  bulletinId: string,
  payload: { choice_type: ParticipationChoiceType; choice_cash_amount?: number },
): Promise<ParticipationBulletin> {
  const { data } = await apiClient.post<ParticipationBulletin>(
    `/api/participation/me/participation-bulletins/${bulletinId}/respond`,
    payload,
  );
  return data;
}

export function choiceLabel(choice?: ParticipationChoiceType | null): string {
  switch (choice) {
    case 'full_cash':
      return 'Totalité en numéraire';
    case 'partial_cash':
      return 'Montant partiel en numéraire';
    case 'full_pee':
      return 'Placement PEE';
    default:
      return '—';
  }
}

export function bulletinStatusLabel(status: string): string {
  switch (status) {
    case 'pending':
      return 'En préparation';
    case 'sent':
      return 'En attente réponse';
    case 'responded':
      return 'Répondu';
    case 'default_pee':
      return 'Défaut PEE';
    case 'cancelled':
      return 'Annulé';
    default:
      return status;
  }
}
