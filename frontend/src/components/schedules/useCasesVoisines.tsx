import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { getCalendarSnapshot } from '@/api/calendar';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import { joursVoisins, numeroDeSemaine, type JourVoisin } from '@/lib/joursVoisins';
import { JourVoisinCell } from '@/components/schedules/JourVoisinCell';

/**
 * Semaine à cheval sur deux mois (retour d'Elsa du 26/11) : les cases des
 * jours des mois voisins, en lecture, pour la première et la dernière semaine
 * de la grille. Commun au tiroir des plannings et à la fiche salarié.
 */
export function useCasesVoisines({
  employeeId,
  annee,
  mois,
  actif,
  isForfaitJour,
  isDirty,
  ouvrirMois,
}: {
  employeeId: string;
  annee: number;
  mois: number;
  actif: boolean;
  isForfaitJour: boolean;
  isDirty: boolean;
  ouvrirMois: (d: { year: number; month: number }) => void;
}): { avant: ReactNode[]; apres: ReactNode[] } {
  const societeActive = useActiveCompanyId();
  const voisins = joursVoisins(annee, mois);
  const lire = (jours: JourVoisin[]) => {
    const m = jours[0];
    return {
      queryKey: ['calendrier-mois-voisin', societeActive, employeeId, m?.annee, m?.mois],
      queryFn: async () =>
        (await getCalendarSnapshot(employeeId, m!.annee, m!.mois, { companyId: societeActive })).data,
      enabled: actif && Boolean(m) && Boolean(employeeId),
      // Relu à chaque affichage : un enregistrement du mois voisin passe hors
      // de ce cache (useCalendar).
      staleTime: 0,
      refetchOnMount: 'always' as const,
    };
  };
  const avant = useQuery(lire(voisins.avant));
  const apres = useQuery(lire(voisins.apres));
  const cases = (jours: JourVoisin[], q: typeof avant) =>
    jours.map((j, i) => (
      <JourVoisinCell
        key={`voisin-${j.annee}-${j.mois}-${j.jour}`}
        date={j.date}
        prevu={q.data?.calendrier_prevu?.find((d) => d.jour === j.jour)}
        reel={q.data?.calendrier_reel?.find((d) => d.jour === j.jour)}
        isForfaitJour={isForfaitJour}
        chargement={q.isLoading}
        erreur={q.isError}
        bloque={isDirty}
        semaine={i === 0 ? numeroDeSemaine(j.date) : undefined}
        onOuvrir={() => ouvrirMois({ year: j.annee, month: j.mois })}
      />
    ));
  return { avant: cases(voisins.avant, avant), apres: cases(voisins.apres, apres) };
}
