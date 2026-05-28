// Page Collaborateur : Mon suivi médical (lecture seule)

import { useMemo } from 'react';
import { Link } from 'react-router-dom';
import { AlertCircle, LifeBuoy, RefreshCw, Stethoscope } from 'lucide-react';
import { EmployeeMedicalKpiBand } from '@/components/medical-follow-up/EmployeeMedicalKpiBand';
import { EmployeeMedicalNextVisitCard } from '@/components/medical-follow-up/EmployeeMedicalNextVisitCard';
import { EmployeeMedicalObligationsList } from '@/components/medical-follow-up/EmployeeMedicalObligationsList';
import { EmployeeMedicalFollowUpSkeleton } from '@/components/skeletons/EmployeeMedicalFollowUpSkeleton';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { useEmployeeMedicalObligationsQuery } from '@/hooks/queries/useEmployeeMedicalObligationsQuery';
import { getMedicalFollowUpErrorMessage } from '@/lib/employeeMedicalFollowUp';
import { countMedicalObligations } from '@/lib/medicalFollowUpLabels';
import {
  EmployeePageHeader,
  EmployeePageShell,
} from '@/components/employee/EmployeePageHeader';

function PageHeader({
  onRefresh,
  isRefreshing,
}: {
  onRefresh: () => void;
  isRefreshing: boolean;
}) {
  return (
    <EmployeePageHeader
      title="Mon suivi médical"
      description="Vos prochaines visites et l'historique de suivi médical"
      icon={<Stethoscope />}
      actions={
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-2"
          onClick={onRefresh}
          disabled={isRefreshing}
        >
          <RefreshCw className={isRefreshing ? 'h-4 w-4 animate-spin' : 'h-4 w-4'} />
          Actualiser
        </Button>
      }
    />
  );
}

export default function EmployeeMedicalFollowUp() {
  const { data: obligations = [], isLoading, isError, error, refetch, isFetching } =
    useEmployeeMedicalObligationsQuery();

  const counts = useMemo(() => countMedicalObligations(obligations), [obligations]);
  const upcomingCount = Math.max(0, counts.active - counts.overdue);

  if (isLoading && obligations.length === 0) {
    return <EmployeeMedicalFollowUpSkeleton />;
  }

  if (isError) {
    const message = getMedicalFollowUpErrorMessage(error);
    return (
      <EmployeePageShell>
        <PageHeader onRefresh={() => void refetch()} isRefreshing={isFetching} />
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
            <span>{message}</span>
            <Button type="button" variant="outline" size="sm" onClick={() => void refetch()}>
              Réessayer
            </Button>
          </AlertDescription>
        </Alert>
      </EmployeePageShell>
    );
  }

  return (
    <EmployeePageShell>
      <PageHeader onRefresh={() => void refetch()} isRefreshing={isFetching} />

      {counts.overdue > 0 && (
        <Alert className="border-destructive/40 bg-destructive/5">
          <AlertCircle className="h-4 w-4 text-destructive" />
          <AlertDescription>
            {counts.overdue === 1
              ? 'Vous avez 1 visite médicale en retard.'
              : `Vous avez ${counts.overdue} visites médicales en retard.`}{' '}
            Contactez les RH ou la médecine du travail pour planifier votre passage.
          </AlertDescription>
        </Alert>
      )}

      {obligations.length === 0 ? (
        <Card>
          <CardContent className="pt-6 space-y-4">
            <p className="text-muted-foreground">
              Aucune obligation de suivi médical pour le moment. Les visites sont calculées à
              partir de votre contrat et des visites déjà enregistrées par votre employeur.
            </p>
            <p className="text-sm text-muted-foreground">
              En cas de question, contactez les ressources humaines.
            </p>
            <Button variant="outline" size="sm" className="gap-2" asChild>
              <Link to="/support">
                <LifeBuoy className="h-4 w-4" />
                Contacter le support
              </Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <>
          <EmployeeMedicalKpiBand
            overdue={counts.overdue}
            upcoming={upcomingCount}
            completed={counts.completed}
          />
          <EmployeeMedicalNextVisitCard obligations={obligations} />
          <EmployeeMedicalObligationsList obligations={obligations} />
        </>
      )}
    </EmployeePageShell>
  );
}
