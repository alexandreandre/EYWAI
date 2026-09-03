import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { useRhSidebarTaskBadges } from '@/hooks/useRhSidebarTaskBadges';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import {
  countSchedulesToEnter,
  fetchAllEmployeesOverview,
  type SchedulesEmployeeInput,
} from '@/lib/schedulesOverview';
import { filterPresentEmployees } from '@/lib/employmentStatus';
import { moisDePaieParDefaut } from '@/features/payroll/utils/payrollMonth';

export const PAYROLL_WORKFLOW_URLS = [
  '/schedules',
  '/leaves',
  '/expenses',
] as const;

export function useCanLaunchPayroll(enabled = true) {
  const { getCount, isPayrollPipelineLoading } = useRhSidebarTaskBadges(enabled);
  const companyId = useActiveCompanyId();

  // Le verrou plannings vise le MOIS DE PAIE en préparation (jusqu'au 15 : le
  // mois précédent), pas le mois calendaire courant — début septembre, la paie
  // d'août ne doit pas être bloquée par les calendriers vierges de septembre.
  // Même queryKey que la pastille sidebar : le cache est partagé quand les
  // deux mois coïncident (après le 15).
  const { year, month } = moisDePaieParDefaut(new Date());
  const schedulesQuery = useQuery({
    queryKey: ['schedules', 'sidebar-badges', companyId, year, month],
    queryFn: async () => {
      const empRes =
        await apiClient.get<SchedulesEmployeeInput[]>('/api/employees');
      const employees = filterPresentEmployees(empRes.data ?? []);
      if (employees.length === 0) return 0;
      const rows = await fetchAllEmployeesOverview(employees, year, month);
      return countSchedulesToEnter(rows);
    },
    enabled: enabled && !!companyId,
    staleTime: 5 * 60_000,
  });

  const autresEtapesSoldees = (['/leaves', '/expenses'] as const).every(
    (url) => getCount(url) === 0,
  );
  const isLoading = isPayrollPipelineLoading || schedulesQuery.isPending;
  const canLaunchPayroll =
    !isLoading && autresEtapesSoldees && schedulesQuery.data === 0;

  return {
    canLaunchPayroll,
    isLoading,
  };
}
