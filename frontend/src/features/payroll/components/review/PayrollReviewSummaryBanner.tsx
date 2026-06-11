import { cn } from '@/lib/utils';
import { CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';
import type { PreflightAnomaliesResponse } from '@/api/payrollPreflight';

interface PayrollReviewSummaryBannerProps {
  data: PreflightAnomaliesResponse | undefined;
  isLoading: boolean;
  className?: string;
}

export function PayrollReviewSummaryBanner({
  data,
  isLoading,
  className,
}: PayrollReviewSummaryBannerProps) {
  if (isLoading) {
    return (
      <div
        className={cn(
          'flex items-center gap-3 rounded-xl border border-border bg-muted/30 px-4 py-3',
          className,
        )}
      >
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden />
        <p className="text-sm text-muted-foreground">Chargement de la revue des anomalies…</p>
      </div>
    );
  }

  const total = data?.total ?? 0;
  const open = data?.total_open ?? 0;
  const treated = data?.total_treated ?? 0;
  const allClear = total === 0 || open === 0;

  return (
    <div
      className={cn(
        'rounded-xl border px-4 py-3',
        allClear
          ? 'border-success/30 bg-success/5'
          : 'border-amber-300/60 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-950/20',
        className,
      )}
    >
      <div className="flex flex-wrap items-start gap-3">
        {allClear ? (
          <CheckCircle2 className="h-5 w-5 shrink-0 text-success" aria-hidden />
        ) : (
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden />
        )}
        <div className="min-w-0 flex-1">
          <p className="text-sm font-semibold text-foreground">
            {total === 0
              ? 'Aucune anomalie détectée pour ce mois'
              : allClear
                ? 'Revue des anomalies terminée'
                : 'Lançable avec réserves'}
          </p>
          <p className="text-xs text-muted-foreground">
            {total === 0
              ? 'Vous pouvez lancer la paie sereinement.'
              : allClear
                ? `${treated} anomalie${treated > 1 ? 's' : ''} traitée${treated > 1 ? 's' : ''} ou justifiée${treated > 1 ? 's' : ''}.`
                : `${open} anomalie${open > 1 ? 's' : ''} ouverte${open > 1 ? 's' : ''} sur ${total} — ${treated} traitée${treated > 1 ? 's' : ''}.`}
          </p>
        </div>
        {data && data.counts.bloquant > 0 && open > 0 && (
          <span className="shrink-0 rounded-md bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800 dark:bg-red-950 dark:text-red-200">
            {data.counts.bloquant} bloquant{data.counts.bloquant > 1 ? 's' : ''}
          </span>
        )}
        {data && data.counts.a_verifier > 0 && open > 0 && (
          <span className="shrink-0 rounded-md bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800 dark:bg-amber-950 dark:text-amber-200">
            {data.counts.a_verifier} à vérifier
          </span>
        )}
      </div>
    </div>
  );
}
