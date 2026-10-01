import apiClient from '@/api/apiClient';
import { payloadJournalEcran } from '@/features/employees/utils/creationSalarie';

/** Journal d’une erreur d’écran : jamais bloquant, jamais de donnée personnelle. */
export async function signalerErreurEcran(brut: {
  ecran: string;
  action: string;
  message: string;
  pile?: string;
}): Promise<void> {
  try {
    await apiClient.post('/api/client-errors', payloadJournalEcran(brut));
  } catch {
    /* un échec du journal ne doit pas masquer l’échec métier */
  }
}
