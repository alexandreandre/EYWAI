import { LogOut } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { BandeauSortieGuidee } from '@/features/payroll/utils/sortieGuidee';

type Props = {
  bandeaux: BandeauSortieGuidee[];
  onCreerLeDepart: (employeeId: string) => void;
};

export function BandeauxSortieGuidee({ bandeaux, onCreerLeDepart }: Props) {
  if (bandeaux.length === 0) return null;

  return (
    <div className="space-y-2">
      {bandeaux.map((bandeau) => (
        <Alert
          key={bandeau.employeeId}
          className="border-amber-200 bg-amber-50/80"
          data-testid="bandeau-sortie-guidee"
        >
          <LogOut className="h-4 w-4 text-amber-700" />
          <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between text-amber-900/90">
            <p>{bandeau.message}</p>
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="shrink-0 border-amber-300 bg-white"
              data-testid="creer-le-depart"
              onClick={() => onCreerLeDepart(bandeau.employeeId)}
            >
              {bandeau.bouton}
            </Button>
          </AlertDescription>
        </Alert>
      ))}
    </div>
  );
}
