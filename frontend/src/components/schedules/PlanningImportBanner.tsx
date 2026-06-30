import { CalendarCheck, FileSearch, Loader2, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  planningImportProgressLabel,
  planningImportProgressPercent,
  type PlanningImportJob,
} from '@/hooks/planningImportJobStore';
import { cn } from '@/lib/utils';

type Props = {
  jobs: PlanningImportJob[];
  onReview?: (job: PlanningImportJob) => void;
  onCancel?: (job: PlanningImportJob) => void;
  onDismiss?: (job: PlanningImportJob) => void;
  className?: string;
};

export function PlanningImportBanner({ jobs, onReview, onCancel, onDismiss, className }: Props) {
  if (jobs.length === 0) return null;

  return (
    <div className={cn('space-y-2', className)}>
      {jobs.map((job) => {
        const isActive =
          job.status !== 'committed' &&
          job.status !== 'completed' &&
          job.status !== 'failed' &&
          job.status !== 'cancelled';
        const isParseReady = job.kind === 'parse' && job.status === 'completed';
        const isFailed = job.status === 'failed';
        const isCancelled = job.status === 'cancelled';
        const isCancelling = job.status === 'cancelling';
        const canCancel =
          isActive && job.kind === 'commit' && Boolean(job.batchId) && Boolean(onCancel);
        const percent = planningImportProgressPercent(job);

        return (
          <div
            key={job.localId}
            className={cn(
              'flex items-center gap-3 rounded-lg border px-3 py-2 text-sm',
              isFailed
                ? 'border-destructive/30 bg-destructive/[0.04]'
                : 'border-border/70 bg-muted/25',
            )}
          >
            {isActive ? (
              <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
            ) : isParseReady ? (
              <FileSearch className="h-4 w-4 shrink-0 text-primary" />
            ) : (
              <CalendarCheck
                className={cn(
                  'h-4 w-4 shrink-0',
                  isFailed ? 'text-destructive' : 'text-emerald-600',
                )}
              />
            )}

            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="truncate font-medium text-foreground">
                  {isActive
                    ? job.kind === 'parse'
                      ? 'Analyse calendrier'
                      : 'Import calendrier'
                    : isFailed
                      ? 'Import calendrier interrompu'
                      : isCancelled
                        ? 'Import calendrier annulé'
                        : isParseReady
                          ? 'Analyse calendrier prête'
                          : 'Calendrier enregistré'}
                </span>
                <span className="truncate text-xs text-muted-foreground">{job.label}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                {job.status === 'committed'
                  ? `${job.employeesProcessed ?? 0} salarié(s), ${(job.totalDaysWritten ?? 0).toLocaleString('fr-FR')} jour(s) de calendrier prévu.`
                  : isParseReady
                    ? 'Ouvrez la revue pour vérifier les rapprochements et enregistrer.'
                  : planningImportProgressLabel(job)}
              </p>
              {(isActive || job.status === 'committed' || isParseReady) && (
                <Progress value={percent} className="h-1" />
              )}
            </div>

            <div className="flex shrink-0 items-center gap-1">
              {isParseReady && onReview ? (
                <Button type="button" size="sm" variant="secondary" onClick={() => onReview(job)}>
                  Revoir
                </Button>
              ) : null}
              {canCancel ? (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground"
                  disabled={isCancelling}
                  onClick={() => onCancel?.(job)}
                >
                  {isCancelling ? 'Annulation…' : 'Annuler'}
                </Button>
              ) : null}
              {!isActive && onDismiss ? (
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  className="h-8 w-8 text-muted-foreground"
                  aria-label="Masquer"
                  onClick={() => onDismiss(job)}
                >
                  <X className="h-4 w-4" />
                </Button>
              ) : null}
            </div>
          </div>
        );
      })}
    </div>
  );
}
