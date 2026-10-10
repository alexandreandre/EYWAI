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
import { Link } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { JoursASaisirListe } from '@/features/payroll/components/JoursASaisirListe';
import {
  ChoixHeuresSurArret,
  HeuresSurArretSansJours,
} from '@/features/payroll/components/ChoixHeuresSurArret';
import type {
  PayrollGenerationJob,
  PayrollGenerationRefusal,
} from '@/features/payroll/hooks/usePayrollGeneration';
import {
  REFUSAL_DIALOG_LABELS,
  estForcable,
  refusForcablesEnGroupe,
} from '@/features/payroll/utils/generationGuards';
import { aDesJoursAEffacer, lienCalendrierDuSalarie } from '@/features/payroll/utils/heuresSurArret';
import { monthYearLabel } from '@/features/payroll/utils/payrollMonth';

type PayrollGenerationRefusalDialogProps = {
  open: boolean;
  refusals: PayrollGenerationRefusal[];
  /** Bulletins générés (avec ou sans alerte) sur la même passe. */
  generatedCount: number;
  /** Relance les refusés avec le flag de forçage — clic explicite uniquement. */
  onForce: () => void;
  /** Relance un job sans forçage : après l'effacement des heures, ou pour réessayer. */
  onRetry: (job: PayrollGenerationJob) => void;
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
  onRetry,
  onDismiss,
}: PayrollGenerationRefusalDialogProps) {
  if (refusals.length === 0) return null;

  const single = refusals.length === 1 ? refusals[0] : null;
  const calendarCount = refusals.filter(
    (r) => r.code === 'calendrier_incomplet'
  ).length;
  const validatedCount = refusals.filter((r) => r.code === 'bulletin_valide').length;
  const heuresCount = refusals.filter(
    (r) => r.code === 'heures_sur_jour_d_arret'
  ).length;
  const illisiblesCount = refusals.filter((r) => r.code === 'arrets_illisibles').length;
  const forcables = refusForcablesEnGroupe(refusals);

  const title = single
    ? REFUSAL_DIALOG_LABELS[single.code].title
    : `${refusals.length} bulletins refusés`;
  const actionLabel = single
    ? REFUSAL_DIALOG_LABELS[single.code].actionLabel
    : 'Forcer les refusés';
  // Forçable : le bouton force. Arrêts illisibles : il réessaie. Heures sur un
  // arrêt : pas de bouton, le choix est dans le corps du dialogue.
  const actionPrincipale: 'forcer' | 'reessayer' | null = single
    ? estForcable(single.code)
      ? 'forcer'
      : single.code === 'arrets_illisibles'
        ? 'reessayer'
        : null
    : forcables.length > 0
      ? 'forcer'
      : null;

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
              bulletin validé : {validatedCount}, heures sur un jour d’arrêt :{' '}
              {heuresCount}, arrêts illisibles : {illisiblesCount}).
            </AlertDialogDescription>
          )}
        </AlertDialogHeader>

        {single?.code === 'calendrier_incomplet' && single.details && (
          <JoursASaisirListe
            details={single.details}
            lienPlanning={lienCalendrierDuSalarie(single.job.employeeId)}
            onLienClick={onDismiss}
          />
        )}

        {single?.code === 'heures_sur_jour_d_arret' &&
          (aDesJoursAEffacer(single.jours) ? (
            <ChoixHeuresSurArret
              employeeId={single.job.employeeId}
              employeeName={single.job.employeeName}
              jours={single.jours}
              onEffacees={() => {
                onRetry(single.job);
              }}
              onModifier={onDismiss}
            />
          ) : (
            <HeuresSurArretSansJours employeeId={single.job.employeeId} onOuvrir={onDismiss} />
          ))}

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
                  {refusal.code === 'calendrier_incomplet' && (
                    <>
                      {' · '}
                      <Link
                        to={lienCalendrierDuSalarie(refusal.job.employeeId)}
                        onClick={onDismiss}
                        className="underline underline-offset-2"
                      >
                        Compléter le planning
                      </Link>
                    </>
                  )}
                </span>
              </div>
            ))}
          </div>
        )}

        {!single &&
          refusals
            .filter((r) => r.code === 'heures_sur_jour_d_arret')
            .map((refusal) => (
              <div
                key={`choix-${refusal.job.employeeId}-${refusal.job.year}-${refusal.job.month}`}
                className="space-y-2 rounded-md border border-border/60 p-3"
              >
                <p className="text-sm font-medium">
                  {refusal.job.employeeName} —{' '}
                  {monthYearLabel(refusal.job.month, refusal.job.year)}
                </p>
                <p className="text-sm text-muted-foreground">{refusal.message}</p>
                {aDesJoursAEffacer(refusal.jours) ? (
                  <ChoixHeuresSurArret
                    employeeId={refusal.job.employeeId}
                    employeeName={refusal.job.employeeName}
                    jours={refusal.jours}
                    onEffacees={() => {
                      onRetry(refusal.job);
                    }}
                    onModifier={onDismiss}
                  />
                ) : (
                  <HeuresSurArretSansJours
                    employeeId={refusal.job.employeeId}
                    onOuvrir={onDismiss}
                  />
                )}
              </div>
            ))}

        {!single &&
          refusals
            .filter((r) => r.code === 'arrets_illisibles')
            .map((refusal) => (
              <div
                key={`retry-${refusal.job.employeeId}-${refusal.job.year}-${refusal.job.month}`}
                className="flex items-center justify-between gap-3 rounded-md border border-border/60 p-3 text-sm"
              >
                <span>{refusal.message}</span>
                <Button type="button" size="sm" variant="outline" onClick={() => onRetry(refusal.job)}>
                  Réessayer
                </Button>
              </div>
            ))}

        {!single && forcables.length > 0 && (
          <p className="text-xs text-muted-foreground">
            Forcer génère malgré un calendrier incomplet. Les heures sur un
            jour d’arrêt et les arrêts illisibles ne se forcent pas.
          </p>
        )}

        {!single && validatedCount > 0 && (
          <p className="text-xs text-muted-foreground" data-testid="valides-pas-en-groupe">
            {validatedCount === 1
              ? 'Un bulletin validé n’est pas régénéré en groupe'
              : `${validatedCount} bulletins validés ne sont pas régénérés en groupe`}
            {' '}: ouvrez chacun depuis son écran pour décider de le régénérer.
          </p>
        )}

        <AlertDialogFooter>
          <AlertDialogCancel onClick={onDismiss}>Fermer</AlertDialogCancel>
          {actionPrincipale === 'forcer' && (
            <AlertDialogAction onClick={onForce}>{actionLabel}</AlertDialogAction>
          )}
          {actionPrincipale === 'reessayer' && single && (
            <AlertDialogAction onClick={() => onRetry(single.job)}>
              {actionLabel}
            </AlertDialogAction>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
