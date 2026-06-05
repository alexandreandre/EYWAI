import { AlertTriangle, Check, Loader2, X } from 'lucide-react';
import { SharkFinBootProgress } from '@/components/SharkFinBootProgress';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type {
  PayrollGenerationLogEntry,
  PayrollGenerationPhase,
} from '@/features/payroll/hooks/usePayrollGeneration';
import { monthYearLabel } from '@/features/payroll/utils/payrollMonth';

type PayrollProgressBarProps = {
  phase: PayrollGenerationPhase;
  progress: number;
  currentLabel: string | null;
  estimatedRemainingSec: number | null;
  log: PayrollGenerationLogEntry[];
  totalJobs?: number;
  completedCount?: number;
  onDismiss?: () => void;
  onCancel?: () => void;
  className?: string;
};

export function PayrollProgressBar({
  phase,
  progress,
  currentLabel,
  estimatedRemainingSec,
  log,
  totalJobs = 0,
  completedCount = 0,
  onDismiss,
  onCancel,
  className,
}: PayrollProgressBarProps) {
  if (phase === 'idle') return null;

  const showFeed = log.length > 0 || currentLabel;
  const canDismiss = phase === 'done' && onDismiss;
  const showCounter = totalJobs > 0;

  return (
    <div
      className={cn(
        'rounded-lg border border-border bg-muted/20 p-4 space-y-3',
        className
      )}
      role="status"
      aria-live="polite"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <p className="text-sm font-medium text-foreground">
            {phase === 'running' ? 'Génération en cours…' : 'Génération terminée'}
          </p>
          {showCounter && (
            <p className="text-xs text-muted-foreground tabular-nums">
              {completedCount} / {totalJobs} bulletin{totalJobs !== 1 ? 's' : ''} traité
              {completedCount !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {phase === 'running' && estimatedRemainingSec != null && estimatedRemainingSec > 0 && (
            <span className="text-xs text-muted-foreground tabular-nums">
              ~{estimatedRemainingSec}s restantes
            </span>
          )}
          {phase === 'running' && onCancel && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-destructive hover:bg-destructive/10 hover:text-destructive"
              onClick={onCancel}
              aria-label="Annuler la génération"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
          {canDismiss && (
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 text-muted-foreground hover:text-foreground"
              onClick={onDismiss}
              aria-label="Fermer le suivi de génération"
            >
              <X className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>

      <SharkFinBootProgress value={progress} determinate />

      {currentLabel && phase === 'running' && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 shrink-0 animate-spin text-cyan-500" aria-hidden />
          <span>{currentLabel}</span>
        </div>
      )}

      {showFeed && (
        <ul className="max-h-[140px] space-y-1 overflow-y-auto text-sm">
          {log.map((entry) => (
            <li key={entry.id} className="flex items-start gap-2">
              {entry.status === 'success' ? (
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-green-100">
                  <Check className="h-3 w-3 text-green-600" aria-hidden />
                </span>
              ) : entry.status === 'warning' ? (
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-amber-100">
                  <AlertTriangle className="h-3 w-3 text-amber-600" aria-hidden />
                </span>
              ) : (
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-red-100">
                  <X className="h-3 w-3 text-red-600" aria-hidden />
                </span>
              )}
              <span className="min-w-0">
                <span className="font-medium">
                  {monthYearLabel(entry.month, entry.year)} — {entry.employeeName}
                </span>
                {entry.status === 'success' ? (
                  <span className="text-muted-foreground"> — c&apos;est fait</span>
                ) : entry.status === 'warning' ? (
                  <span className="text-amber-700 dark:text-amber-400">
                    {' '}
                    — généré avec alerte{entry.warnings && entry.warnings.length > 1 ? 's' : ''}
                    {entry.error ? ` : ${entry.error}` : ''}
                  </span>
                ) : (
                  <span className="text-red-600"> — {entry.error}</span>
                )}
              </span>
            </li>
          ))}
        </ul>
      )}

      {phase === 'done' && !log.some((entry) => entry.status === 'error') && (
        <p className="text-xs text-muted-foreground">
          {log.some((entry) => entry.status === 'warning')
            ? 'Des bulletins ont été générés avec des alertes — ouvrez-les pour corriger.'
            : 'Fermeture automatique dans quelques secondes…'}
        </p>
      )}
    </div>
  );
}
