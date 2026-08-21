import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import type { PayrollGenerationRefusal } from '@/features/payroll/hooks/usePayrollGeneration';
import { REFUSAL_DIALOG_LABELS } from '@/features/payroll/utils/generationGuards';
import { monthYearLabel } from '@/features/payroll/utils/payrollMonth';

type PayrollGenerationRefusalDialogProps = {
  open: boolean;
  refusals: PayrollGenerationRefusal[];
  /** Bulletins générés (avec ou sans alerte) sur la même passe. */
  generatedCount: number;
  /** Relance les refusés avec le flag de forçage — clic explicite uniquement. */
  onForce: () => void;
  onDismiss: () => void;
};

/**
 * Dialogue affiché quand la génération se termine avec des refus de garde
 * (422 calendrier incomplet / 409 bulletin validé).
 *
 * - Un seul refus : dialogue ciblé « Calendrier incomplet » / « Bulletin
 *   validé » avec le message du backend et le bouton de forçage dédié.
 * - Plusieurs refus : récapitulatif « N générés, M refusés (…) » avec la liste
 *   des refusés et l'action « Forcer les refusés ».
 *
 * Le forçage n'est JAMAIS silencieux : il ne part que sur le clic de ce dialogue.
 */
export function PayrollGenerationRefusalDialog({
  open,
  refusals,
  generatedCount,
  onForce,
  onDismiss,
}: PayrollGenerationRefusalDialogProps) {
  if (refusals.length === 0) return null;

  const single = refusals.length === 1 ? refusals[0] : null;
  const calendarCount = refusals.filter(
    (r) => r.code === 'calendrier_incomplet'
  ).length;
  const validatedCount = refusals.filter((r) => r.code === 'bulletin_valide').length;

  const title = single
    ? REFUSAL_DIALOG_LABELS[single.code].title
    : `${refusals.length} bulletins refusés`;
  const actionLabel = single
    ? REFUSAL_DIALOG_LABELS[single.code].actionLabel
    : 'Forcer les refusés';

  return (
    <AlertDialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onDismiss();
      }}
    >
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          {single ? (
            <AlertDialogDescription>
              <span className="font-medium text-foreground">
                {monthYearLabel(single.job.month, single.job.year)} —{' '}
                {single.job.employeeName}
              </span>
              <br />
              {single.message}
              {single.code === 'bulletin_valide' && (
                <>
                  <br />
                  <span className="text-xs">
                    En régénérant, l’ancienne version validée est archivée.
                  </span>
                </>
              )}
            </AlertDialogDescription>
          ) : (
            <AlertDialogDescription>
              {generatedCount} généré{generatedCount !== 1 ? 's' : ''},{' '}
              {refusals.length} refusés (calendrier incomplet : {calendarCount},
              bulletin validé : {validatedCount}).
            </AlertDialogDescription>
          )}
        </AlertDialogHeader>

        {!single && (
          <div className="max-h-[220px] space-y-1 overflow-y-auto rounded-md border border-border/60 bg-muted/20 p-3 text-sm">
            {refusals.map((refusal) => (
              <div
                key={`${refusal.job.employeeId}-${refusal.job.year}-${refusal.job.month}`}
                className="flex items-start justify-between gap-3"
              >
                <span className="min-w-0 truncate font-medium">
                  {refusal.job.employeeName}{' '}
                  <span className="font-normal text-muted-foreground">
                    — {monthYearLabel(refusal.job.month, refusal.job.year)}
                  </span>
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {REFUSAL_DIALOG_LABELS[refusal.code].shortLabel}
                </span>
              </div>
            ))}
          </div>
        )}

        {!single && (
          <p className="text-xs text-muted-foreground">
            Forcer génère malgré un calendrier incomplet et régénère les
            bulletins validés en archivant l’ancienne version.
          </p>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={onDismiss}>Fermer</AlertDialogCancel>
          <AlertDialogAction onClick={onForce}>{actionLabel}</AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
