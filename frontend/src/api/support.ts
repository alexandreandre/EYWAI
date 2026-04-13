// frontend/src/api/support.ts
// API tickets support (JWT + X-Active-Company via apiClient)

import apiClient from './apiClient';

export type TicketUrgency = 'critique' | 'elevee' | 'normale' | 'faible';
export type TicketStatus = 'envoye' | 'en_cours' | 'resolu' | 'cloture';

export interface TicketStatusHistoryItem {
  id: string;
  old_status: string | null;
  new_status: string;
  changed_by: string;
  changed_at: string;
}

/** Réponse liste super admin : jointure Supabase `companies(company_name)`. */
export interface TicketCompanyEmbed {
  company_name?: string;
}

export interface Ticket {
  id: string;
  company_id: string;
  user_id: string;
  user_role: string;
  module: string;
  request_type: string;
  urgency: TicketUrgency;
  description: string;
  context?: string;
  status: TicketStatus;
  created_at: string;
  updated_at: string;
  status_history?: TicketStatusHistoryItem[];
  companies?: TicketCompanyEmbed | TicketCompanyEmbed[] | null;
}

/** Statuts modifiables par le Super Admin (PATCH). */
export type TicketStatusAdminUpdate = 'en_cours' | 'resolu' | 'cloture';

export interface TicketCreate {
  module: string;
  request_type: string;
  urgency: TicketUrgency;
  description: string;
  context?: string;
}

export const createTicket = async (data: TicketCreate): Promise<Ticket> => {
  const response = await apiClient.post<Ticket>('/api/support/tickets', data);
  return response.data;
};

export const getTickets = async (
  filters?: Record<string, string>,
): Promise<Ticket[]> => {
  const response = await apiClient.get<Ticket[]>('/api/support/tickets', {
    params: filters,
  });
  return response.data;
};

export const getTicketDetail = async (ticketId: string): Promise<Ticket> => {
  const response = await apiClient.get<Ticket>(`/api/support/tickets/${ticketId}`);
  return response.data;
};

export const updateTicketStatus = async (
  ticketId: string,
  status: TicketStatusAdminUpdate,
): Promise<Ticket> => {
  const response = await apiClient.patch<Ticket>(
    `/api/support/tickets/${ticketId}/status`,
    { status },
  );
  return response.data;
};
