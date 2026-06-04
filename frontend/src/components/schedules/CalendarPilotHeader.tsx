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
import { pageTitleClassName } from '@/components/layout';
import { Calculator, Loader2, Sparkles } from 'lucide-react';
import type { GlobalOverviewKpis } from '@/lib/schedulesOverview';
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
  onOpenAssistedFill: () => void;
  isCalculatingPayroll: boolean;
  canCalculatePayroll: boolean;
  isLoading?: boolean;
}

export function CalendarPilotHeader({
  year,
  month,
  onYearChange,
  onMonthChange,
  kpis,
  onCalculatePayroll,
  onOpenAssistedFill,
  isCalculatingPayroll,
  canCalculatePayroll,
  isLoading = false,
}: CalendarPilotHeaderProps) {
  const periodLabel = `${MONTHS[month - 1]} ${year}`;

  return (
    <div className="-mx-6 px-6 py-3 bg-background/95 backdrop-blur border-b space-y-3 lg:-mx-8 lg:px-8">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className={pageTitleClassName}>
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

          <Button
            type="button"
            variant="outline"
            onClick={onOpenAssistedFill}
            className="h-9"
          >
            <Sparkles className="mr-2 h-4 w-4 text-primary" />
            Remplissage assisté
          </Button>

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

      <div className="space-y-1" aria-busy={isLoading}>
        <div className="flex justify-between text-xs text-muted-foreground">
          {isLoading ? (
            <Skeleton className="h-3.5 w-40" />
          ) : kpis.aSaisir > 0 ? (
            <span>
              Reste à saisir :{' '}
              <span className="font-medium text-foreground">
                {kpis.aSaisir} calendrier{kpis.aSaisir > 1 ? 's' : ''}
              </span>{' '}
              sur {kpis.total}
            </span>
          ) : (
            <span className="font-medium text-emerald-600">
              Tous les calendriers sont saisis
            </span>
          )}
          {!isLoading && <span>{kpis.progressPercent} %</span>}
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
