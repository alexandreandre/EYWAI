import { AlertTriangle } from 'lucide-react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { Employee } from '@/features/employee-detail/types';

type Props = {
  employee: Employee;
  onOpenEdit: () => void;
};

/**
 * Ce que la loi impose et que la fiche n'a pas (prévoyance des cadres, audit du
 * 03/11/2026). Le serveur dit le constat et le geste ; tant qu'il reste une
 * alerte, le bulletin du salarié ne se génère pas.
 */
export function EmployeeAlertesPaieBanner({ employee, onOpenEdit }: Props) {
  const alertes = (employee.alertes_paie ?? []).filter((a) => a?.message?.trim());
  if (alertes.length === 0) return null;

  return (
    <Alert variant="default" className="border-amber-300 bg-amber-50/80">
      <AlertTriangle className="h-4 w-4 text-amber-700" />
      <AlertTitle className="text-amber-900">Prévoyance obligatoire à compléter</AlertTitle>
      <AlertDescription className="space-y-3 text-amber-900/90">
        {alertes.map((alerte) => (
          <p key={alerte.code}>{alerte.message}</p>
        ))}
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="border-amber-300 bg-white"
          onClick={onOpenEdit}
        >
          Modifier la fiche
        </Button>
      </AlertDescription>
    </Alert>
  );
}
