import { useQuery } from '@tanstack/react-query';
import { getDashboardCounts } from '@/api/certifications';
import { getOverdueCount } from '@/api/legalObligations';
import { getBudget } from '@/api/trainingBudget';
import { getAchievementRate } from '@/api/objectives';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export function useFormationDashboardQueries(year = new Date().getFullYear()) {
  const companyId = useActiveCompanyId();
  const enabled = Boolean(companyId);

  const certs = useQuery({
    queryKey: queryKeys.formationDashboardCerts(companyId),
    queryFn: getDashboardCounts,
    enabled,
  });

  const overdue = useQuery({
    queryKey: queryKeys.formationDashboardOverdue(companyId),
    queryFn: getOverdueCount,
    enabled,
  });

  const budget = useQuery({
    queryKey: queryKeys.formationDashboardBudget(companyId, year),
    queryFn: () => getBudget(year),
    enabled,
  });

  const achievement = useQuery({
    queryKey: queryKeys.formationDashboardAchievement(companyId, year),
    queryFn: () => getAchievementRate(year),
    enabled,
  });

  return { certs, overdue, budget, achievement };
}
