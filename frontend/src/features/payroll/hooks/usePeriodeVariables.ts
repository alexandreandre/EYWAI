import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getPeriodeVariables,
  getSurchargesPeriodeVariables,
  putPeriodeVariables,
} from '@/api/periodeVariables';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { queryKeys } from '@/lib/queryKeys';

export function usePeriodeVariables(year: number, month: number, enabled = true) {
  const companyId = useActiveCompanyId();

  return useQuery({
    queryKey: queryKeys.periodeVariables(companyId, year, month),
    queryFn: () => getPeriodeVariables(year, month),
    enabled: enabled && year > 0 && month >= 1 && month <= 12,
    staleTime: 30_000,
  });
}

export function useEnregistrerPeriodeVariables(year: number, month: number) {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (fin: string) => putPeriodeVariables(year, month, fin),
    onSuccess: (data) => {
      queryClient.setQueryData(queryKeys.periodeVariables(companyId, year, month), data);
      queryClient.invalidateQueries({
        queryKey: queryKeys.surchargesPeriodeVariables(companyId, year),
      });
    },
  });
}

export function useSurchargesPeriodeVariables(year: number) {
  const companyId = useActiveCompanyId();

  return useQuery({
    queryKey: queryKeys.surchargesPeriodeVariables(companyId, year),
    queryFn: () => getSurchargesPeriodeVariables(year),
    enabled: year > 0,
    staleTime: 60_000,
  });
}
