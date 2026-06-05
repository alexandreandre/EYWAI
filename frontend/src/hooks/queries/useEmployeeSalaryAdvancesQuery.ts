import { useQuery } from '@tanstack/react-query';
import {
  getMyAdvanceAvailable,
  getMySalaryAdvances,
  type AdvanceAvailableAmount,
  type SalaryAdvance,
} from '@/api/saisiesAvances';
import { queryKeys } from '@/lib/queryKeys';

export type EmployeeSalaryAdvancesData = {
  advances: SalaryAdvance[];
  available: AdvanceAvailableAmount;
};

export function useEmployeeSalaryAdvancesQuery(userId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.employeeSalaryAdvances(userId),
    queryFn: async (): Promise<EmployeeSalaryAdvancesData> => {
      const [advances, available] = await Promise.all([
        getMySalaryAdvances(),
        getMyAdvanceAvailable(),
      ]);
      return { advances, available };
    },
    enabled: Boolean(userId),
  });
}
