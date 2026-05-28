import { useQuery } from '@tanstack/react-query';
import { getMyMonthPlanning } from '@/api/planning';
import { useCompany } from '@/contexts/CompanyContext';
import { groupShiftsByDayNumber } from '@/lib/employeeCalendarPlanning';

export function useEmployeeMonthShifts(year: number, month: number, enabled = true) {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? '';

  const query = useQuery({
    queryKey: ['my-planning-month', companyId, year, month],
    queryFn: () => getMyMonthPlanning(companyId, year, month),
    enabled: enabled && Boolean(companyId),
    staleTime: 60_000,
  });

  const shiftsByDay = groupShiftsByDayNumber(query.data ?? []);

  return {
    shifts: query.data ?? [],
    shiftsByDay,
    isLoading: query.isLoading,
    isError: query.isError,
    refetch: query.refetch,
  };
}
