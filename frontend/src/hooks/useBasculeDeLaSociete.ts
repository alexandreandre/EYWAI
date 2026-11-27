import { useQuery } from '@tanstack/react-query';
import { fetchCompanyDetails } from '@/api/company';
import { getPeriodeVariables } from '@/api/periodeVariables';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { basculeDeLaSociete, type BasculeDuMois } from '@/lib/basculeCalendrier';

/**
 * La bascule de reprise de la société active (premier jour de la paie Martine),
 * pour la fiche salarié. `null` sans reprise, ou illisible : rien n'est retiré.
 */
export function useBasculeDeLaSociete(enabled = true): BasculeDuMois | null {
  const companyId = useActiveCompanyId();
  const { data } = useQuery({
    queryKey: ['bascule-calendrier', companyId],
    queryFn: async () => {
      const reprise = await fetchCompanyDetails()
        .then((d) => d.company_data.reprise_paie ?? null)
        .catch((): null => null);
      return basculeDeLaSociete(reprise, getPeriodeVariables);
    },
    enabled: enabled && Boolean(companyId),
    staleTime: 10 * 60_000,
  });
  return data ?? null;
}
