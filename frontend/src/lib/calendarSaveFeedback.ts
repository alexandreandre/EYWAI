import { CalendarBatchError } from './calendarBatch';
import { accord, pluriel } from './pluriel';

export function calendarSaveFailureMessage(error: unknown): string {
  if (error instanceof CalendarBatchError) {
    return `${pluriel(error.completed, 'calendrier')} ${accord(error.completed, 'confirmé')} sur ${error.total}. ${calendarSaveFailureMessage(error.failure)}`;
  }
  const detail = (error as { response?: { data?: { detail?: { code?: string; message?: string; stage?: string; confirmed?: string[] } } } })?.response?.data?.detail;
  if (detail?.code === 'calendar_conflict' || detail?.code === 'calendar_busy' || detail?.code === 'calendar_unavailable') {
    return detail.message ?? 'Le calendrier ne peut pas être enregistré. Vos saisies restent affichées.';
  }
  if (detail?.code === 'calendar_save_failed') {
    const confirmed = detail.confirmed ?? [];
    if (detail.stage === 'planned') return 'Le prévu n’a pas pu être confirmé. Conservez vos saisies avant de recharger le calendrier.';
    if (detail.stage === 'actual' && confirmed.includes('planned')) return 'Le prévu a été enregistré, mais le réel n’a pas pu être confirmé. Conservez vos saisies avant de recharger le calendrier.';
    if (detail.stage === 'payroll') return 'Les saisies ont été enregistrées, mais le calcul n’a pas pu être confirmé. Rechargez le calendrier avant de contrôler le bulletin.';
    return detail.message ?? 'La confirmation de l’enregistrement a échoué. Conservez vos saisies avant de recharger le calendrier.';
  }
  return 'L’enregistrement n’a pas pu être confirmé. Vos saisies restent affichées ; conservez-les avant de recharger le calendrier.';
}
