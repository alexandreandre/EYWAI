import { useRhSidebarTaskBadges } from '@/hooks/useRhSidebarTaskBadges';
import { usePreflightAnomaliesCount } from '@/features/payroll/hooks/usePreflightAnomaliesCount';

export const PAYROLL_WORKFLOW_URLS = [
  '/schedules',
  '/leaves',
  '/expenses',
  '/saisies',
  '/salary-seizures',
  '/salary-advances',
] as const;

export function useCanLaunchPayroll(enabled = true) {
  const { getCount, isLoading } = useRhSidebarTaskBadges(enabled);
  const now = new Date();
  const { openAnomaliesCount, isLoading: preflightLoading } = usePreflightAnomaliesCount(
    now.getFullYear(),
    now.getMonth() + 1,
    enabled,
  );
  const canLaunchPayroll =
    !isLoading && PAYROLL_WORKFLOW_URLS.every((url) => getCount(url) === 0);

  return {
    canLaunchPayroll,
    isLoading: isLoading || preflightLoading,
    openAnomaliesCount,
  };
}
