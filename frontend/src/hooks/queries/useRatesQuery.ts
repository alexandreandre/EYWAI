import { useQuery } from '@tanstack/react-query';
import apiClient from '@/api/apiClient';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export function useRatesQuery(enabled = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.rates(companyId),
    queryFn: async () => {
      const res = await apiClient.get('/api/rates/all');
      return res.data;
    },
    enabled: enabled && Boolean(companyId),
  });
}
