import { Percent } from 'lucide-react';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import type { Employee } from '@/features/employee-detail/types';

interface EmployeePasSettingsCardProps {
  employeeId: string;
  employee: Employee;
  canEdit?: boolean;
  onEmployeeUpdated: (employee: Employee) => void;
}

function readPasSettings(employee: Employee) {
  const pas = employee.specificites_paie?.prelevement_a_la_source;
  const taux = typeof pas?.taux === 'number' ? pas.taux : 0;
  const isPersonnalise = pas?.is_personnalise ?? taux > 0;
  return {
    isPersonnalise,
    taux,
    typeTaux: pas?.type_taux ?? null,
    periode: pas?.periode ?? null,
  };
}

/**
 * D'où vient le taux appliqué.
 *
 * La nomenclature DSN distingue le taux personnalisé que la DGFiP transmet
 * (01) du barème appliqué en attendant sa réponse (13). La distinction compte :
 * un salarié au barème n'est pas mal paramétré, il attend son premier compte
 * rendu métier.
 */
function origineLibelle(typeTaux: string | null): string | null {
  if (!typeTaux) return null;
  if (typeTaux === '01') return 'Taux transmis par la DGFiP';
  if (typeTaux === '13') return 'Taux barème, en attente du taux DGFiP';
  return `Type de taux ${typeTaux}`;
}

function periodeLibelle(periode: string | null): string | null {
  if (!periode) return null;
  const [annee, mois] = periode.split('-');
  const libelles = [
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
    'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
  ];
  const index = Number(mois) - 1;
  return libelles[index] ? `Reçu sur la période de ${libelles[index]} ${annee}` : periode;
}

/**
 * Carte en LECTURE SEULE : le taux PAS est transmis par la DGFiP (compte
 * rendu métier des déclarations), on n'a pas le droit de le modifier à la
 * main — la saisie manuelle a été retirée à la demande de la déclarante
 * (07/09/2026). Le dépannage reste possible côté admin/API si nécessaire.
 */
export function EmployeePasSettingsCard({ employee }: EmployeePasSettingsCardProps) {
  const current = readPasSettings(employee);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center text-base">
          <Percent className="mr-2 h-5 w-5 text-primary" />
          Prélèvement à la source (PAS)
        </CardTitle>
        <CardDescription>
          Taux transmis par l&apos;administration fiscale (DGFiP). Appliqué sur les prochains bulletins.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1 rounded-md border bg-muted/30 p-3 text-sm">
          <p className="font-medium tabular-nums">
            {current.isPersonnalise || current.taux > 0
              ? `${current.taux} %`
              : 'Aucun taux connu — 0 % appliqué'}
          </p>
          {origineLibelle(current.typeTaux) ? (
            <p className="text-muted-foreground">{origineLibelle(current.typeTaux)}</p>
          ) : null}
          {periodeLibelle(current.periode) ? (
            <p className="text-xs text-muted-foreground">
              {periodeLibelle(current.periode)}
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">
              Période d&apos;origine inconnue : déposez la dernière déclaration depuis
              l&apos;écran Prélèvement à la source pour la dater.
            </p>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          Ce taux n&apos;est pas modifiable à la main : il est mis à jour par les
          retours DGFiP (compte rendu métier). Sans taux connu, 0&nbsp;% est
          appliqué en attendant le premier retour.
        </p>
      </CardContent>
    </Card>
  );
}
