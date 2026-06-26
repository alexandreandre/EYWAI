import { AlertTriangle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';

type Props = {
  employeeId: string;
  exitId?: string | null;
  fullName: string;
};

export function EmployeePendingExitBanner({ employeeId, exitId, fullName }: Props) {
  const exitsHref = exitId
    ? `/employee-exits?exitId=${encodeURIComponent(exitId)}`
    : `/employee-exits?employeeId=${encodeURIComponent(employeeId)}`;

  return (
    <Alert variant="default" className="border-amber-200 bg-amber-50/80">
      <AlertTriangle className="h-4 w-4 text-amber-700" />
      <AlertTitle className="text-amber-900">Départ à finaliser</AlertTitle>
      <AlertDescription className="space-y-3 text-amber-900/90">
        <p>
          {fullName} a été signalé(e) comme absent(e) de la DSN. Un processus de sortie est
          ouvert — complétez la clôture (documents, solde, checklist) dans le module Départs.
        </p>
        <Button asChild size="sm" variant="outline" className="border-amber-300 bg-white">
          <Link to={exitsHref}>Ouvrir le dossier de départ</Link>
        </Button>
      </AlertDescription>
    </Alert>
  );
}
