import { useQuery } from '@tanstack/react-query';

import { lireReglageActivitePartielle } from '@/api/activitePartielle';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';

/**
 * La société a-t-elle l'activité partielle activée ? Le calendrier ne propose
 * le type « Activité partielle » qu'à cette condition. Une lecture refusée
 * (salarié, droits) vaut « non ».
 */
export function useActivitePartielleActive(): boolean {
  const companyId = useActiveCompanyId();
  const { data } = useQuery({
    queryKey: ['activite-partielle-reglage', companyId],
    queryFn: lireReglageActivitePartielle,
    enabled: Boolean(companyId),
    staleTime: 5 * 60_000,
    retry: false,
  });
  return Boolean(data?.active);
}
