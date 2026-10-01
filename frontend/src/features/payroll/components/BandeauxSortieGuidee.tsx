import { FileText, LogOut } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import type { BandeauSortieGuidee } from '@/features/payroll/utils/sortieGuidee';

type Props = {
  bandeaux: BandeauSortieGuidee[];
  onCreerLeDepart: (employeeId: string) => void;
  onGenererBulletin: (employeeId: string) => void;
};

export function BandeauxSortieGuidee({
  bandeaux,
  onCreerLeDepart,
  onGenererBulletin,
}: Props) {
  if (bandeaux.length === 0) return null;

  return (
    <div className="space-y-2">
      {bandeaux.map((bandeau) => {
        const creer = bandeau.etape === 'creer_depart';
        return (
          <Alert
            key={bandeau.employeeId}
            className="border-amber-200 bg-amber-50/80"
            data-testid="bandeau-sortie-guidee"
          >
            {creer ? (
              <LogOut className="h-4 w-4 text-amber-700" />
            ) : (
              <FileText className="h-4 w-4 text-amber-700" />
            )}
            <AlertDescription className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between text-amber-900/90">
              <p>{bandeau.message}</p>
              {creer ? (
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
              ) : bandeau.peutGenerer ? (
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  className="shrink-0 border-amber-300 bg-white"
                  data-testid="generer-bulletin-sortie"
                  onClick={() => onGenererBulletin(bandeau.employeeId)}
                >
                  {bandeau.bouton}
                </Button>
              ) : (
                <p
                  className="shrink-0 text-sm text-muted-foreground"
                  data-testid="generer-bulletin-bloque"
                >
                  {bandeau.raisonBlocage}
                </p>
              )}
            </AlertDescription>
          </Alert>
        );
      })}
    </div>
  );
}
