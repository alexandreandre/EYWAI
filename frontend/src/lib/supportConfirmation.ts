/** État de navigation après création réussie d'un ticket support. */
export type SupportConfirmationLocationState = {
  ticketId: string;
};

const SESSION_KEY = 'eywai_support_confirmation_ticket';

export function persistSupportConfirmationTicket(ticketId: string): void {
  try {
    sessionStorage.setItem(SESSION_KEY, ticketId);
  } catch {
    /* sessionStorage indisponible (navigation privée stricte) */
  }
}

export function readSupportConfirmationTicket(): string | null {
  try {
    return sessionStorage.getItem(SESSION_KEY);
  } catch {
    return null;
  }
}

export function clearSupportConfirmationTicket(): void {
  try {
    sessionStorage.removeItem(SESSION_KEY);
  } catch {
    /* ignore */
  }
}
