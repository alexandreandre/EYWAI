import { Loader2, Upload, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  progressLabel,
  progressPercent,
  type PointageImportJob,
} from '@/hooks/pointageImportJobStore';
import { cn } from '@/lib/utils';

interface PointageImportBannerProps {
  jobs: PointageImportJob[];
  onReview: (job: PointageImportJob) => void;
  onCancel?: (job: PointageImportJob) => void;
  onDismiss?: (job: PointageImportJob) => void;
  className?: string;
}

export function PointageImportBanner({
  jobs,
  onReview,
  onCancel,
  onDismiss,
  className,
}: PointageImportBannerProps) {
  if (jobs.length === 0) return null;

  return (
    <div className={cn('space-y-2', className)}>
      {jobs.map((job) => {
        const isActive = job.status === 'queued' || job.status === 'extracting';
        const isReady =
          job.status === 'completed' &&
          job.proposal &&
          job.proposal.employees.length > 0 &&
          !job.reviewDismissed;
        const isFailed = job.status === 'failed';

        if (!isActive && !isReady && !isFailed) return null;

        const percent = isActive ? progressPercent(job.progress) : isReady ? 100 : 0;

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
            ) : (
              <Upload className="h-4 w-4 shrink-0 text-muted-foreground" />
            )}

            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
                <span className="truncate font-medium text-foreground">
                  {isReady ? 'Import pointages prêt' : 'Import pointages'}
                </span>
                <span className="truncate text-xs text-muted-foreground">{job.label}</span>
              </div>
              <p className="text-xs text-muted-foreground">
                {isReady
                  ? `${job.proposal?.employees.length ?? 0} salarié(s) — ouvrez la revue pour valider`
                  : isFailed
                    ? job.errorMessage ?? "L'analyse a échoué."
                    : progressLabel(job)}
              </p>
              {(isActive || isReady) && (
                <Progress value={percent} className="h-1" />
              )}
            </div>

            <div className="flex shrink-0 items-center gap-1">
              {isReady && (
                <Button type="button" size="sm" variant="secondary" onClick={() => onReview(job)}>
                  Revoir
                </Button>
              )}
              {isActive && onCancel && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="text-muted-foreground"
                  onClick={() => onCancel(job)}
                >
                  Annuler
                </Button>
              )}
              {(isReady || isFailed) && onDismiss && (
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
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
