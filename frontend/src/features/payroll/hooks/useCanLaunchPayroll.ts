import { useRhSidebarTaskBadges } from '@/hooks/useRhSidebarTaskBadges';

export const PAYROLL_WORKFLOW_URLS = [
  '/schedules',
  '/leaves',
  '/expenses',
] as const;

export function useCanLaunchPayroll(enabled = true) {
  const { getCount, isLoading } = useRhSidebarTaskBadges(enabled);
  const canLaunchPayroll =
    !isLoading && PAYROLL_WORKFLOW_URLS.every((url) => getCount(url) === 0);

  return {
    canLaunchPayroll,
    isLoading,
  };
}
