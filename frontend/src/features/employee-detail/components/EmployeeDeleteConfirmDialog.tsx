import { useEffect, useState } from 'react';
import { Loader2, Trash2 } from 'lucide-react';
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { DropdownMenuItem } from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  getEmployeeDeletionImpact,
  type EmployeeDeletionImpact,
} from '@/api/employees';

const STATIC_REMOVED_ITEMS = [
  'Fiche collaborateur et historique salarial',
  'Compte de connexion (si aucun autre accès)',
  'Bulletins de paie et simulations',
  'Avances, acomptes et saisies sur salaire',
  'Absences, congés et IJSS',
  'Plannings, badgeuse et pointages',
  'Documents (contrat, pièce d\'identité, attestations)',
  'Entretiens, formations et notes de frais',
  'Processus de sortie en cours',
];

type EmployeeDeleteConfirmDialogProps = {
  employeeId: string;
  employeeFullName: string;
  onDelete: () => void | Promise<void>;
  isDeleting?: boolean;
};

export function EmployeeDeleteConfirmDialog({
  employeeId,
  employeeFullName,
  onDelete,
  isDeleting = false,
}: EmployeeDeleteConfirmDialogProps) {
  const [open, setOpen] = useState(false);
  const [impact, setImpact] = useState<EmployeeDeletionImpact | null>(null);
  const [impactLoading, setImpactLoading] = useState(false);
  const [impactError, setImpactError] = useState<string | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [nameInput, setNameInput] = useState('');

  const nameMatches =
    nameInput.trim().toLowerCase() === employeeFullName.trim().toLowerCase();
  const canConfirm = confirmed && nameMatches && !isDeleting && !impactLoading;

  useEffect(() => {
    if (!open) {
      setConfirmed(false);
      setNameInput('');
      setImpact(null);
      setImpactError(null);
      return;
    }

    let cancelled = false;
    setImpactLoading(true);
    setImpactError(null);
    void getEmployeeDeletionImpact(employeeId)
      .then((data) => {
        if (!cancelled) setImpact(data);
      })
      .catch(() => {
        if (!cancelled) {
          setImpactError('Impossible de charger le détail des données liées.');
        }
      })
      .finally(() => {
        if (!cancelled) setImpactLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, employeeId]);

  const handleConfirm = async () => {
    if (!canConfirm) return;
    await onDelete();
    setOpen(false);
  };

  return (
    <AlertDialog open={open} onOpenChange={(next) => !isDeleting && setOpen(next)}>
      <AlertDialogTrigger asChild>
        <DropdownMenuItem
          className="text-destructive focus:text-destructive"
          onSelect={(e) => e.preventDefault()}
        >
          <Trash2 className="mr-2 h-4 w-4" />
          Supprimer le collaborateur
        </DropdownMenuItem>
      </AlertDialogTrigger>
      <AlertDialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
        <AlertDialogHeader>
          <AlertDialogTitle>Supprimer définitivement ce collaborateur ?</AlertDialogTitle>
          <AlertDialogDescription asChild>
            <div className="space-y-4 text-left text-sm text-muted-foreground">
              <p>
                Vous êtes sur le point de supprimer{' '}
                <span className="font-medium text-foreground">{employeeFullName}</span>.
                Cette action est <strong className="text-foreground">irréversible</strong>.
              </p>

              <div>
                <p className="mb-2 font-medium text-foreground">Seront supprimés :</p>
                <ul className="list-inside list-disc space-y-1">
                  {STATIC_REMOVED_ITEMS.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>

              {impactLoading ? (
                <div className="flex items-center gap-2 text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Analyse des données existantes…
                </div>
              ) : null}

              {impactError ? (
                <p className="text-sm text-amber-700 dark:text-amber-400">{impactError}</p>
              ) : null}

              {impact?.summary_lines?.length ? (
                <div className="rounded-md border border-destructive/30 bg-destructive/5 p-3">
                  <p className="mb-1 text-sm font-medium text-destructive">
                    Données actuellement enregistrées :
                  </p>
                  <ul className="list-inside list-disc space-y-0.5 text-sm">
                    {impact.summary_lines.map((line) => (
                      <li key={line}>{line}</li>
                    ))}
                  </ul>
                </div>
              ) : null}

              <div className="space-y-3 pt-1">
                <div className="flex items-start gap-2">
                  <Checkbox
                    id="delete-confirm-checkbox"
                    checked={confirmed}
                    onCheckedChange={(v) => setConfirmed(v === true)}
                    disabled={isDeleting}
                  />
                  <Label htmlFor="delete-confirm-checkbox" className="leading-snug">
                    Je comprends que cette suppression est définitive et irréversible.
                  </Label>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="delete-confirm-name">
                    Tapez <span className="font-medium">{employeeFullName}</span> pour confirmer
                  </Label>
                  <Input
                    id="delete-confirm-name"
                    value={nameInput}
                    onChange={(e) => setNameInput(e.target.value)}
                    placeholder={employeeFullName}
                    disabled={isDeleting}
                    autoComplete="off"
                  />
                </div>
              </div>
            </div>
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel disabled={isDeleting}>Annuler</AlertDialogCancel>
          <Button
            type="button"
            variant="destructive"
            disabled={!canConfirm}
            onClick={() => void handleConfirm()}
          >
            {isDeleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Suppression…
              </>
            ) : (
              'Supprimer définitivement'
            )}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
