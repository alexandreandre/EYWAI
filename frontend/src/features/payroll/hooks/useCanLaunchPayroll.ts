import { useRhSidebarTaskBadges } from '@/hooks/useRhSidebarTaskBadges';
import { etatVerrouPaie, peutLancerLaPaie } from '@/features/payroll/lib/controleAvantPaie';

// Le badge « /schedules » est calé sur le MOIS DE PAIE en préparation
// (moisDePaieParDefaut dans useRhPendingTasks) : le verrou et la pastille
// sidebar lisent le même compteur — un seul balayage, une seule vérité.
export const PAYROLL_WORKFLOW_URLS = [
  '/schedules',
  '/leaves',
  '/expenses',
] as const;

export function useCanLaunchPayroll(enabled = true) {
  const { getCount, isPayrollPipelineLoading, isPayrollPipelineError, retryFailed } =
    useRhSidebarTaskBadges(enabled);
  // Un compteur en erreur vaut 0 : sans l'état d'erreur, le verrou
  // s'ouvrait en silence quand une requête échouait.
  const etat = etatVerrouPaie({
    enChargement: isPayrollPipelineLoading,
    enErreur: isPayrollPipelineError,
    compteurs: PAYROLL_WORKFLOW_URLS.map((url) => getCount(url)),
  });

  return {
    canLaunchPayroll: peutLancerLaPaie(etat),
    isLoading: isPayrollPipelineLoading,
    /** Une source du parcours n'a pas répondu : « Contrôle indisponible ». */
    isError: etat === 'indisponible',
    etat,
    retry: retryFailed,
  };
}
