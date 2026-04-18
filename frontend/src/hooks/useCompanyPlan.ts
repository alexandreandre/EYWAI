import { useQuery } from '@tanstack/react-query';

import apiClient from '@/api/apiClient';

const QK_COMPANY_PLAN = ['company', 'plan'] as const;

export type CompanyPlanDto = {
  is_premium: boolean;
};

export function useCompanyPlan() {
  const { data, isLoading, isFetching } = useQuery({
    queryKey: [...QK_COMPANY_PLAN],
    queryFn: async () => {
      const r = await apiClient.get<CompanyPlanDto>('/api/company/plan');
      return r.data;
    },
  });

  return {
    isPremium: Boolean(data?.is_premium),
    isLoading: isLoading || isFetching,
  };
}
