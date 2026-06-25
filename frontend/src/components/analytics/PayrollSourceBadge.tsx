import { Badge } from '@/components/ui/badge';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

export type PayrollSource = 'payslip' | 'dsn' | 'none';

type PayrollSourceBadgeProps = {
  source: PayrollSource;
  sourceLabel?: string;
  partial?: boolean;
  className?: string;
};

function badgeLabel(source: PayrollSource, partial?: boolean): string {
  if (partial && source === 'dsn') return 'Import DSN partiel';
  switch (source) {
    case 'payslip':
      return 'Bulletins validés';
    case 'dsn':
      return 'Masse déclarée (DSN)';
    default:
      return 'Donnée indisponible';
  }
}

function tooltipText(source: PayrollSource, sourceLabel?: string, partial?: boolean): string {
  if (sourceLabel?.trim()) return sourceLabel;
  if (source === 'dsn') {
    return partial
      ? 'Donnée déclarée DSN — certains salariés sans brut extrait'
      : 'Donnée déclarée DSN — estimée / déclarée';
  }
  if (source === 'payslip') return 'Calculée à partir des bulletins validés dans EYWAI';
  return 'Importez une DSN ou générez les bulletins pour afficher la masse du mois';
}

const variantClass: Record<PayrollSource, string> = {
  payslip: 'border-emerald-200 bg-emerald-50 text-emerald-900',
  dsn: 'border-amber-200 bg-amber-50 text-amber-950',
  none: 'border-muted bg-muted/40 text-muted-foreground',
};

export function PayrollSourceBadge({
  source,
  sourceLabel,
  partial,
  className,
}: PayrollSourceBadgeProps) {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge
            variant="outline"
            className={cn('font-normal text-xs', variantClass[source], className)}
          >
            {badgeLabel(source, partial)}
          </Badge>
        </TooltipTrigger>
        <TooltipContent side="top" className="max-w-xs text-xs">
          {tooltipText(source, sourceLabel, partial)}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
