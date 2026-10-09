import { getUserErrorMessage } from '@/lib/errorMessages';

const LIBELLES: Record<string, string> = {
  pending: 'À valider',
  validated: 'Validée',
};

/** Statut d'une décision d'heures sup en français ; jamais le code brut. */
export function libelleStatutDecision(statut: string | null | undefined): string {
  return (statut && LIBELLES[statut]) || '—';
}

export function messageEchecDecision(erreur: unknown): string {
  return getUserErrorMessage(
    erreur,
    'La décision n’a pas été enregistrée. Réessayez dans un instant.',
  );
}
