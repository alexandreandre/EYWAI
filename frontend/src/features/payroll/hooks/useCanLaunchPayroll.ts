import { useRhSidebarTaskBadges } from '@/hooks/useRhSidebarTaskBadges';

// Le badge « /schedules » est calé sur le MOIS DE PAIE en préparation
// (moisDePaieParDefaut dans useRhPendingTasks) : le verrou et la pastille
// sidebar lisent le même compteur — un seul balayage, une seule vérité.
export const PAYROLL_WORKFLOW_URLS = [
  '/schedules',
  '/leaves',
  '/expenses',
] as const;

export function useCanLaunchPayroll(enabled = true) {
  const { getCount, isPayrollPipelineLoading } = useRhSidebarTaskBadges(enabled);
  const canLaunchPayroll =
    !isPayrollPipelineLoading &&
    PAYROLL_WORKFLOW_URLS.every((url) => getCount(url) === 0);

  return {
    canLaunchPayroll,
    isLoading: isPayrollPipelineLoading,
  };
}
