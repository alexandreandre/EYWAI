import { cn } from '@/lib/utils';
import type { DsnCoverageTimelineMonth } from '@/api/dsnImport';
import { isDsnMonthImported } from '../lib/coveragePresentation';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

const MONTH_LABELS = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];

const STATE_STYLES: Record<string, string> = {
  covered: 'bg-emerald-500 text-white border-emerald-600',
  missing: 'bg-amber-400 text-amber-950 border-amber-500',
  future: 'bg-muted text-muted-foreground border-border',
  native: 'bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-900 dark:text-slate-300',
  preview: 'bg-sky-500 text-white border-sky-600',
};

const STATE_LABELS: Record<string, string> = {
  covered: 'Importé',
  missing: 'Manquant',
  future: 'À venir',
  native: 'Paie Martine - import externe non attendu',
  preview: 'En analyse',
};

export function DsnCoverageTimeline({
  timeline,
  compact = false,
  importedPeriods = [],
  className,
}: {
  timeline: DsnCoverageTimelineMonth[];
  compact?: boolean;
  importedPeriods?: readonly string[];
  className?: string;
}) {
  if (!timeline.length) return null;

  return (
    <TooltipProvider delayDuration={200}>
      <div className={cn('flex flex-wrap gap-1.5', className)}>
        {timeline.map((m) => (
          <Tooltip key={m.period}>
            <TooltipTrigger asChild>
              <div
                className={cn(
                  'flex items-center justify-center rounded-md border font-medium',
                  STATE_STYLES[m.state] ?? STATE_STYLES.future,
                  compact ? 'h-6 w-6 text-[10px]' : 'h-8 w-8 text-xs',
                )}
                aria-label={`${MONTH_LABELS[m.month - 1]} ${m.period} — ${STATE_LABELS[m.state] ?? m.state}${m.state !== 'covered' && isDsnMonthImported(m, importedPeriods) ? ' — DSN déjà importée' : ''}`}
              >
                {MONTH_LABELS[m.month - 1]}
                {m.state !== 'covered' && isDsnMonthImported(m, importedPeriods) && <span aria-hidden className="ml-0.5">✓</span>}
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p className="font-medium">{m.period}</p>
              <p className="text-xs text-muted-foreground">{STATE_LABELS[m.state] ?? m.state}</p>
              {m.state !== 'covered' && isDsnMonthImported(m, importedPeriods) && <p className="text-xs">DSN déjà importée.</p>}
            </TooltipContent>
          </Tooltip>
        ))}
      </div>
    </TooltipProvider>
  );
}

export function dsnStatusLabel(status: string): string {
  switch (status) {
    case 'ok':
      return 'À jour';
    case 'late':
      return 'En attente';
    case 'missing':
      return 'Retard';
    case 'never':
      return 'Jamais importée';
    case 'not_applicable':
      return 'Paie Martine';
    default:
      return status;
  }
}

export function dsnStatusVariant(
  status: string,
): 'success' | 'warning' | 'destructive' | 'secondary' | 'outline' {
  switch (status) {
    case 'ok':
      return 'success';
    case 'late':
      return 'warning';
    case 'missing':
    case 'never':
      return 'destructive';
    case 'not_applicable':
      return 'secondary';
    default:
      return 'outline';
  }
}
