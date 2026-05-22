import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Progress } from '@/components/ui/progress';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Calculator, Loader2 } from 'lucide-react';
import type { GlobalOverviewKpis } from '@/lib/schedulesOverview';
import { cn } from '@/lib/utils';
import { Skeleton } from '@/components/ui/skeleton';

const MONTHS = [
  'Janvier',
  'Février',
  'Mars',
  'Avril',
  'Mai',
  'Juin',
  'Juillet',
  'Août',
  'Septembre',
  'Octobre',
  'Novembre',
  'Décembre',
];

interface CalendarPilotHeaderProps {
  year: number;
  month: number;
  onYearChange: (year: number) => void;
  onMonthChange: (month: number) => void;
  kpis: GlobalOverviewKpis;
  onCalculatePayroll: () => void;
  isCalculatingPayroll: boolean;
  canCalculatePayroll: boolean;
  isLoading?: boolean;
}

function KpiCard({
  label,
  value,
  sub,
  variant,
  isLoading,
}: {
  label: string;
  value: string;
  sub?: string;
  variant?: 'default' | 'warning' | 'danger';
  isLoading?: boolean;
}) {
  return (
    <div
      className={cn(
        'rounded-lg border bg-card px-3 py-2 min-w-[6.5rem]',
        !isLoading && variant === 'warning' && 'border-amber-300/80 bg-amber-50/50 dark:bg-amber-950/20',
        !isLoading && variant === 'danger' && 'border-destructive/30 bg-destructive/5'
      )}
    >
      <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
      {isLoading ? (
        <>
          <Skeleton className="h-7 w-20 mt-0.5" />
          {sub && <Skeleton className="h-3 w-24 mt-1.5" />}
        </>
      ) : (
        <>
          <p className="text-lg font-semibold tabular-nums">{value}</p>
          {sub && <p className="text-[10px] text-muted-foreground">{sub}</p>}
        </>
      )}
    </div>
  );
}

export function CalendarPilotHeader({
  year,
  month,
  onYearChange,
  onMonthChange,
  kpis,
  onCalculatePayroll,
  isCalculatingPayroll,
  canCalculatePayroll,
  isLoading = false,
}: CalendarPilotHeaderProps) {
  const periodLabel = `${MONTHS[month - 1]} ${year}`;

  return (
    <div className="sticky top-0 z-30 -mx-6 px-6 py-3 bg-background/95 backdrop-blur border-b space-y-3 lg:-mx-8 lg:px-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Calendriers — {periodLabel}
          </h1>
          <p className="text-sm text-muted-foreground mt-0.5">
            Pilotage de la saisie mensuelle et clôture paie
          </p>
        </div>

        <div className="flex flex-wrap items-end gap-3">
          <div className="grid gap-1">
            <Label className="text-xs">Mois</Label>
            <Select value={String(month)} onValueChange={(v) => onMonthChange(Number(v))}>
              <SelectTrigger className="w-[140px] h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MONTHS.map((m, i) => (
                  <SelectItem key={i} value={String(i + 1)}>
                    {m}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-1">
            <Label className="text-xs">Année</Label>
            <Select value={String(year)} onValueChange={(v) => onYearChange(Number(v))}>
              <SelectTrigger className="w-[100px] h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {[year - 1, year, year + 1, year + 2].map((y) => (
                  <SelectItem key={y} value={String(y)}>
                    {y}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <TooltipProvider>
            <Tooltip>
              <TooltipTrigger asChild>
                <span>
                  <Button
                    onClick={onCalculatePayroll}
                    disabled={!canCalculatePayroll || isCalculatingPayroll}
                    className="h-9"
                  >
                    {isCalculatingPayroll ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <Calculator className="mr-2 h-4 w-4" />
                    )}
                    Calculer la paie du mois
                  </Button>
                </span>
              </TooltipTrigger>
              {!canCalculatePayroll && (
                <TooltipContent>
                  <p className="max-w-xs text-sm">
                    Tous les calendriers du mois doivent être saisis avant de lancer le calcul
                    paie ({kpis.saisis}/{kpis.total} saisis).
                  </p>
                </TooltipContent>
              )}
            </Tooltip>
          </TooltipProvider>
        </div>
      </div>

      <div className="flex flex-wrap gap-2" aria-busy={isLoading}>
        <KpiCard
          label="Saisis"
          value={`${kpis.saisis} / ${kpis.total}`}
          sub={`${kpis.progressPercent} % du mois`}
          isLoading={isLoading}
        />
        <KpiCard
          label="À saisir"
          value={String(kpis.aSaisir)}
          variant={kpis.aSaisir > 0 ? 'warning' : 'default'}
          isLoading={isLoading}
        />
        <KpiCard
          label="Avec écart"
          value={String(kpis.avecEcart)}
          variant={kpis.avecEcart > 0 ? 'warning' : 'default'}
          isLoading={isLoading}
        />
        <KpiCard
          label="Conflits absences"
          value={String(kpis.conflitsAbsences)}
          variant={kpis.conflitsAbsences > 0 ? 'danger' : 'default'}
          isLoading={isLoading}
        />
        <KpiCard
          label="H. totales"
          value={`${kpis.heuresFaitesTotal.toFixed(0)} / ${kpis.heuresPrevuesTotal.toFixed(0)} h`}
          sub="faites / prévues"
          isLoading={isLoading}
        />
      </div>

      <div className="space-y-1">
        <div className="flex justify-between text-xs text-muted-foreground">
          <span>Progression de saisie</span>
          {isLoading ? (
            <Skeleton className="h-3.5 w-8" />
          ) : (
            <span>{kpis.progressPercent} %</span>
          )}
        </div>
        {isLoading ? (
          <Skeleton className="h-2 w-full" />
        ) : (
          <Progress value={kpis.progressPercent} className="h-2" />
        )}
      </div>
    </div>
  );
}
