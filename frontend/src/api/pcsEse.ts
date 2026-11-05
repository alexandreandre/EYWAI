import apiClient from '@/api/apiClient';
import type { PropositionPcs, RubriquePcs } from '@/features/pcs-ese/pcsEse';

export async function getReferentielPcsEse(): Promise<RubriquePcs[]> {
  const response = await apiClient.get<RubriquePcs[]>('/api/pcs-ese/referentiel');
  return response.data;
}

export async function getPropositionPcsEse(params: {
  poste: string;
  statut: string;
  employee_id?: string;
}): Promise<PropositionPcs> {
  const response = await apiClient.get<PropositionPcs>('/api/pcs-ese/proposition', { params });
  return response.data;
}
