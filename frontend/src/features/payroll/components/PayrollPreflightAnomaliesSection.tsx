import { useState } from 'react';
import { AlertTriangle, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { PreflightAnomaly } from '@/api/payrollPreflight';
import {
  countOpenAnomalies,
  PREFLIGHT_ANOMALY_TYPE_LABELS,
  verifyPathForAnomaly,
} from '@/features/payroll/components/preflightLabels';

interface PayrollPreflightAnomaliesSectionProps {
  anomalies: PreflightAnomaly[];
  isLoading?: boolean;
  onVerify?: (path: string) => void;
  className?: string;
}

export function PayrollPreflightAnomaliesSection({
  anomalies,
  isLoading = false,
  onVerify,
  className,
}: PayrollPreflightAnomaliesSectionProps) {
  const [expanded, setExpanded] = useState(false);
  const openAnomalies = anomalies.filter((a) => a.status === 'a_traiter');
  const openCount = openAnomalies.length;

  if (isLoading) {
    return (
      <div
        className={cn(
          'flex items-center gap-2 rounded-lg border border-border bg-muted/30 px-3 py-2 text-xs text-muted-foreground',
          className,
        )}
      >
        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
        Vérification des anomalies…
      </div>
    );
  }

  if (openCount === 0) {
    return null;
  }

  return (
    <div
      className={cn(
        'overflow-hidden rounded-lg border border-amber-300/60 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-950/20',
        className,
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center gap-2 px-3 py-2.5 text-left"
        aria-expanded={expanded}
      >
        <AlertTriangle
          className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-400"
          aria-hidden
        />
        <span className="min-w-0 flex-1 text-sm font-medium text-amber-900 dark:text-amber-100">
          {openCount} anomalie{openCount > 1 ? 's' : ''} détectée{openCount > 1 ? 's' : ''}
        </span>
        {expanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-300" aria-hidden />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-amber-700 dark:text-amber-300" aria-hidden />
        )}
      </button>

      {expanded && (
        <ul className="divide-y divide-amber-200/80 border-t border-amber-200/80 dark:divide-amber-500/20 dark:border-amber-500/20">
          {openAnomalies.map((anomaly) => (
            <li
              key={anomaly.id}
              className="flex items-start justify-between gap-2 px-3 py-2.5"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {anomaly.employee_name}
                </p>
                <p className="mt-0.5 line-clamp-2 text-xs text-muted-foreground">
                  {PREFLIGHT_ANOMALY_TYPE_LABELS[anomaly.type]}
                  {anomaly.message ? ` — ${anomaly.message}` : ''}
                </p>
              </div>
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-8 shrink-0 border-amber-300/70 bg-background hover:bg-muted/60"
                onClick={() => onVerify?.(verifyPathForAnomaly(anomaly))}
              >
                Vérifier
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export { countOpenAnomalies };
