import { cn } from '@/lib/utils';
import type { DsnCoverageTimelineMonth } from '@/api/dsnImport';
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
  preview: 'bg-sky-500 text-white border-sky-600',
};

const STATE_LABELS: Record<string, string> = {
  covered: 'Importé',
  missing: 'Manquant',
  future: 'À venir',
  preview: 'En analyse',
};

export function DsnCoverageTimeline({
  timeline,
  compact = false,
  className,
}: {
  timeline: DsnCoverageTimelineMonth[];
  compact?: boolean;
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
                aria-label={`${MONTH_LABELS[m.month - 1]} ${m.period} — ${STATE_LABELS[m.state] ?? m.state}`}
              >
                {MONTH_LABELS[m.month - 1]}
              </div>
            </TooltipTrigger>
            <TooltipContent>
              <p className="font-medium">{m.period}</p>
              <p className="text-xs text-muted-foreground">{STATE_LABELS[m.state] ?? m.state}</p>
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
      return 'Paie EYWAI';
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
