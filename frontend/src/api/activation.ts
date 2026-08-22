// API du lien d'activation : endpoints publics (page /activation) et
// invitation RH (fiche salarié). Le jeton en clair ne transite que du lien
// e-mail vers ces appels ; il n'est jamais stocké côté client.

import apiClient from '@/api/apiClient';

export interface InvitationStatus {
  status: 'jamais_invite' | 'invite' | 'active';
  invited_at?: string | null;
  expires_at?: string | null;
  expired: boolean;
  email?: string | null; // toujours masqué par le backend
}

export interface InvitationSent {
  invited_at: string;
  email: string; // masqué
  expires_at: string;
}

export interface ActivationVerifyResult {
  prenom: string;
  societe: string;
}

export async function getInvitationStatus(
  employeeId: string,
): Promise<InvitationStatus> {
  const response = await apiClient.get(`/api/employees/${employeeId}/invitation`);
  return response.data;
}

export async function inviteEmployee(employeeId: string): Promise<InvitationSent> {
  const response = await apiClient.post(`/api/employees/${employeeId}/invitation`);
  return response.data;
}

export async function verifyActivationToken(
  token: string,
): Promise<ActivationVerifyResult> {
  const response = await apiClient.post('/api/activation/verify', { token });
  return response.data;
}

export async function completeActivation(
  token: string,
  password: string,
): Promise<{ message: string }> {
  const response = await apiClient.post('/api/activation/complete', {
    token,
    password,
  });
  return response.data;
}
