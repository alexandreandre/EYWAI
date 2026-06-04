import type { ObligationListItem } from '@/api/medicalFollowUp';
import { getApiErrorStatus, getUserErrorMessage } from '@/lib/errorMessages';
import {
  hasMedicalOverdue,
  isDueWithinDays,
  isObligationOverdue,
} from '@/lib/medicalFollowUpLabels';

export const MEDICAL_FOLLOW_UP_ME_QUERY_KEY = ['medical-follow-up', 'me'] as const;

export const MEDICAL_ME_STALE_TIME_MS = 5 * 60 * 1000;

export type MedicalObligationFilter = 'all' | 'upcoming' | 'completed';

export function filterMedicalObligations(
  obligations: ObligationListItem[],
  filter: MedicalObligationFilter
): ObligationListItem[] {
  if (filter === 'all') return obligations;
  if (filter === 'completed') {
    return obligations.filter((o) => o.status === 'realisee');
  }
  return obligations.filter((o) => o.status !== 'realisee' && o.status !== 'annulee');
}

/** Pastille sidebar : retard ou échéance dans les 30 prochains jours (hors réalisées/annulées). */
export function shouldShowEmployeeMedicalNavBadge(
  obligations: ObligationListItem[] | undefined
): boolean {
  if (!obligations?.length) return false;
  if (hasMedicalOverdue(obligations)) return true;
  return obligations.some(
    (o) =>
      o.status !== 'realisee' &&
      o.status !== 'annulee' &&
      o.due_date &&
      !isObligationOverdue(o) &&
      isDueWithinDays(o.due_date, 30)
  );
}

export function getMedicalFollowUpErrorMessage(error: unknown): string {
  if (getApiErrorStatus(error) === 403) {
    return "Le suivi médical n'est pas activé pour votre entreprise.";
  }
  return getUserErrorMessage(error, 'Impossible de charger le suivi médical.');
}
