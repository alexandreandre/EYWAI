import { useQuery } from '@tanstack/react-query';
import { fetchAllRates } from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';
import { useActiveCompanyId } from './useCompanyId';

export function useRatesQuery(enabled = true, requireCompany = true) {
  const companyId = useActiveCompanyId();
  return useQuery({
    queryKey: queryKeys.rates(companyId),
    queryFn: fetchAllRates,
    // Le référentiel de taux est global ; les admins plateforme (sans entreprise
    // active) doivent pouvoir le consulter sans dépendre d'un company_id.
    enabled: enabled && (requireCompany ? Boolean(companyId) : true),
    staleTime: 0,
  });
}
