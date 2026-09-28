/**
 * Le dossier de départ d'un salarié parti, depuis sa fiche.
 *
 * Une fois le départ clôturé (ou clos d'office par la réconciliation DSN), la
 * fiche ne menait plus à rien : en mode paie, l'onglet Documents ne montre que
 * les bulletins et le bandeau « Départ à finaliser » est masqué. Les documents
 * de sortie (certificat de travail, attestation France Travail, solde de tout
 * compte) restaient introuvables pour qui ne connaissait pas le module Départs.
 */
import { useQuery } from '@tanstack/react-query';
import { FileText } from 'lucide-react';
import { Link } from 'react-router-dom';
import { exitTypeLabels, getEmployeeExits, type ExitType } from '@/api/employeeExits';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

type Props = { employeeId: string };

const dateFr = (iso?: string | null) =>
  iso ? new Date(`${iso.slice(0, 10)}T00:00:00`).toLocaleDateString('fr-FR') : null;

export function EmployeeExitDossierBanner({ employeeId }: Props) {
  const { data: depart } = useQuery({
    queryKey: ['employee-exits', 'par-salarie', employeeId],
    queryFn: async () => {
      const departs = await getEmployeeExits({ employee_id: employeeId });
      return (
        departs
          .filter((d) => d.status !== 'annulee')
          .sort((a, b) => String(b.last_working_day ?? '').localeCompare(String(a.last_working_day ?? '')))[0] ??
        null
      );
    },
    // Sans droit sur les départs, pas de bandeau : rien à signaler.
    retry: false,
    staleTime: 60_000,
  });
  if (!depart) return null;

  const le = dateFr(depart.last_working_day);
  const motif = exitTypeLabels[depart.exit_type as ExitType] ?? depart.exit_type;
  return (
    <Alert className="border-slate-200 bg-slate-50" data-testid="dossier-de-depart">
      <FileText className="h-4 w-4" />
      <AlertTitle>Dossier de départ{le ? ` — sortie le ${le}` : ''}</AlertTitle>
      <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <span>
          {motif}. Certificat de travail, attestation France Travail et solde de tout compte se
          génèrent depuis le dossier.
        </span>
        <Button asChild size="sm" variant="outline" className="shrink-0 bg-white">
          <Link to={`/employee-exits?exitId=${encodeURIComponent(depart.id)}`}>Ouvrir le dossier de départ</Link>
        </Button>
      </AlertDescription>
    </Alert>
  );
}
