import { useRhSidebarTaskBadges } from '@/hooks/useRhSidebarTaskBadges';

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
