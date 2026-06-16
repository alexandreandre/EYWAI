import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, Check, Loader2, Plus } from 'lucide-react';
import {
  fetchDsnAdminCoverageMatrix,
  type DsnCoverageMatrixCompany,
  type DsnCoverageTimelineMonth,
} from '@/api/dsnImport';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';
import { dsnStatusLabel, dsnStatusVariant } from './DsnCoverageTimeline';

const MONTH_SHORT = ['J', 'F', 'M', 'A', 'M', 'J', 'J', 'A', 'S', 'O', 'N', 'D'];
const MONTH_FULL = [
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

const STATE_LABELS: Record<string, string> = {
  covered: 'DSN importée',
  missing: 'Mois manquant',
  future: 'Mois futur',
  preview: 'En analyse',
};

function countCoverage(company: DsnCoverageMatrixCompany) {
  const applicable = company.timeline.filter((m) => m.state !== 'future');
  const covered = applicable.filter((m) => m.state === 'covered').length;
  const expected = applicable.length;
  const pct = expected > 0 ? Math.round((covered / expected) * 100) : 0;
  return { covered, expected, pct };
}

function companyDisplayStatus(company: DsnCoverageMatrixCompany) {
  let status = company.status;
  if (status === 'not_applicable' || status === 'never') {
    status = countCoverage(company).covered === 0 ? 'missing' : status;
  }
  return { label: dsnStatusLabel(status), variant: dsnStatusVariant(status) };
}

function MatrixMonthCell({
  month,
  onClickMissing,
  companyId,
}: {
  month: DsnCoverageTimelineMonth;
  onClickMissing?: (companyId: string, period: string) => void;
  companyId: string;
}) {
  const letter = MONTH_SHORT[month.month - 1] ?? '?';
  const clickable = month.state === 'missing' && Boolean(onClickMissing);

  const content = (
    <div
      role={clickable ? 'button' : undefined}
      tabIndex={clickable ? 0 : undefined}
      onClick={clickable ? () => onClickMissing!(companyId, month.period) : undefined}
      onKeyDown={
        clickable
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onClickMissing!(companyId, month.period);
              }
            }
          : undefined
      }
      className={cn(
        'relative flex h-10 w-10 shrink-0 flex-col items-center justify-center rounded-lg border-2 text-xs font-semibold transition-all sm:h-11 sm:w-11',
        month.state === 'covered' && 'border-emerald-600 bg-emerald-500 text-white shadow-sm shadow-emerald-500/25',
        month.state === 'missing' && 'border-amber-500 bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200',
        month.state === 'future' && 'border-border bg-muted/40 text-muted-foreground/60',
        month.state === 'preview' && 'border-sky-500 bg-sky-500 text-white',
        clickable && 'cursor-pointer hover:scale-105 hover:ring-2 hover:ring-primary/30 focus:outline-none focus:ring-2 focus:ring-primary/40',
      )}
      aria-label={`${MONTH_FULL[month.month - 1]} ${month.period} — ${STATE_LABELS[month.state] ?? month.state}`}
    >
      {month.state === 'covered' ? (
        <>
          <Check className="h-4 w-4 sm:h-[18px] sm:w-[18px]" strokeWidth={3} />
          <span className="sr-only">{letter}</span>
        </>
      ) : month.state === 'missing' ? (
        <>
          <AlertCircle className="mb-0.5 h-3 w-3 opacity-80" />
          <span className="text-[9px] leading-none opacity-90">{letter}</span>
        </>
      ) : (
        <span className="text-[10px] font-medium opacity-70">{letter}</span>
      )}
    </div>
  );

  return (
    <Tooltip>
      <TooltipTrigger asChild>{content}</TooltipTrigger>
      <TooltipContent side="top" className="max-w-[200px]">
        <p className="font-medium">
          {MONTH_FULL[month.month - 1]} {month.period.split('-')[0]}
        </p>
        <p className="text-xs text-muted-foreground">{STATE_LABELS[month.state] ?? month.state}</p>
        {clickable && <p className="mt-1 text-xs text-primary">Cliquer pour importer ce mois</p>}
      </TooltipContent>
    </Tooltip>
  );
}

function CoverageLegend() {
  const items = [
    {
      className: 'border-emerald-600 bg-emerald-500',
      icon: <Check className="h-3 w-3 text-white" strokeWidth={3} />,
      label: 'Importé',
    },
    {
      className: 'border-amber-500 bg-amber-100 dark:bg-amber-950/50',
      icon: <AlertCircle className="h-3 w-3 text-amber-700 dark:text-amber-300" />,
      label: 'Manquant',
    },
    { className: 'border-border bg-muted/40', icon: null, label: 'Futur' },
  ];

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border bg-muted/20 px-3 py-2 text-xs">
      <span className="font-medium text-muted-foreground">Légende</span>
      {items.map((item) => (
        <div key={item.label} className="flex items-center gap-1.5">
          <div
            className={cn(
              'flex h-6 w-6 items-center justify-center rounded border-2 text-[10px] font-semibold',
              item.className,
            )}
          >
            {item.icon}
          </div>
          <span className="text-muted-foreground">{item.label}</span>
        </div>
      ))}
    </div>
  );
}

function CompanyCoverageRow({
  company,
  onCellClick,
  onImportCompany,
}: {
  company: DsnCoverageMatrixCompany;
  onCellClick?: (companyId: string, period: string) => void;
  onImportCompany?: (companyId: string) => void;
}) {
  const { covered, expected, pct } = countCoverage(company);
  const displayStatus = companyDisplayStatus(company);

  return (
    <div className="rounded-xl border bg-card p-3 shadow-sm sm:p-4">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="truncate text-sm font-semibold sm:text-base">
              {company.company_name ?? company.company_id.slice(0, 8)}
            </h3>
            <Badge variant={displayStatus.variant} className="shrink-0 text-xs">
              {displayStatus.label}
            </Badge>
            {company.dsn_sync_mode === 'native' && (
              <Badge variant="outline" className="shrink-0 text-[10px] font-normal">
                Paie EYWAI
              </Badge>
            )}
          </div>
          {company.group_name && (
            <p className="truncate text-xs text-muted-foreground">{company.group_name}</p>
          )}
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <div className="text-right">
            <p className="text-lg font-bold tabular-nums leading-none text-foreground">
              {covered}
              <span className="text-sm font-normal text-muted-foreground">/{expected}</span>
            </p>
            <p className="text-[10px] uppercase tracking-wide text-muted-foreground">mois importés</p>
          </div>
          {onImportCompany && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-8 gap-1"
              title="Importer une DSN mensuelle"
              onClick={() => onImportCompany(company.company_id)}
            >
              <Plus className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">Importer</span>
            </Button>
          )}
        </div>
      </div>

      {expected > 0 && (
        <div className="mb-3 h-2 overflow-hidden rounded-full bg-muted">
          <div
            className={cn(
              'h-full rounded-full transition-all',
              pct === 100 ? 'bg-emerald-500' : pct > 0 ? 'bg-amber-400' : 'bg-destructive/70',
            )}
            style={{ width: `${Math.max(pct, covered === 0 ? 4 : 0)}%` }}
          />
        </div>
      )}

      <div className="overflow-x-auto pb-1">
        <div className="flex min-w-max flex-col gap-1.5">
          <div className="flex gap-1.5 sm:gap-2">
            {company.timeline.map((m) => (
              <div
                key={`h-${m.period}`}
                className="flex h-4 w-10 shrink-0 items-center justify-center text-[10px] font-medium text-muted-foreground sm:w-11"
              >
                {MONTH_SHORT[m.month - 1]}
              </div>
            ))}
          </div>
          <div className="flex gap-1.5 sm:gap-2">
            {company.timeline.map((m) => (
              <MatrixMonthCell
                key={m.period}
                month={m}
                companyId={company.company_id}
                onClickMissing={onCellClick}
              />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

type Props = {
  year: number;
  onCellClick?: (companyId: string, period: string) => void;
  onImportCompany?: (companyId: string) => void;
};

export function DsnCoverageMatrix({ year, onCellClick, onImportCompany }: Props) {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['dsn-admin-matrix', year],
    queryFn: () => fetchDsnAdminCoverageMatrix(year),
  });

  const companies = useMemo(() => {
    const list = data?.companies ?? [];
    return [...list].sort((a, b) => {
      const rank = (s: string) => {
        if (s === 'missing' || s === 'never') return 0;
        if (s === 'late') return 1;
        if (s === 'ok') return 2;
        return 3;
      };
      const diff = rank(a.status) - rank(b.status);
      if (diff !== 0) return diff;
      return (a.company_name ?? '').localeCompare(b.company_name ?? '', 'fr');
    });
  }, [data?.companies]);

  const globalStats = useMemo(() => {
    let totalCovered = 0;
    let lateCount = 0;
    companies.forEach((c) => {
      const { covered } = countCoverage(c);
      totalCovered += covered;
      if (c.status === 'missing' || c.status === 'late' || c.status === 'never') lateCount += 1;
    });
    return { totalCovered, lateCount, companyCount: companies.length };
  }, [companies]);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-3 border-b bg-muted/10 pb-4">
        <div>
          <CardTitle className="text-lg">Couverture DSN {year}</CardTitle>
          <CardDescription>
            Toutes les entreprises — vert = importé, ambre = manquant, gris = futur.
          </CardDescription>
        </div>

        {!isLoading && !isError && companies.length > 0 && (
          <div className="flex flex-wrap gap-3 text-sm">
            <div className="rounded-lg border bg-background px-3 py-2">
              <span className="font-bold tabular-nums text-foreground">{globalStats.companyCount}</span>
              <span className="text-muted-foreground"> entreprise{globalStats.companyCount > 1 ? 's' : ''}</span>
            </div>
            <div className="rounded-lg border bg-background px-3 py-2">
              <span className="font-bold tabular-nums text-emerald-600">{globalStats.totalCovered}</span>
              <span className="text-muted-foreground"> mois importés au total</span>
            </div>
            {globalStats.lateCount > 0 && (
              <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-3 py-2">
                <span className="font-bold tabular-nums text-amber-700 dark:text-amber-400">
                  {globalStats.lateCount}
                </span>
                <span className="text-muted-foreground">
                  {' '}
                  sans couverture complète
                </span>
              </div>
            )}
          </div>
        )}

        <CoverageLegend />
      </CardHeader>

      <CardContent className="pt-4">
        {isLoading ? (
          <div className="flex items-center gap-2 py-12 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Chargement de la couverture…
          </div>
        ) : isError ? (
          <p className="py-8 text-sm text-destructive">Impossible de charger la couverture.</p>
        ) : companies.length === 0 ? (
          <p className="py-8 text-sm text-muted-foreground">Aucune entreprise à afficher.</p>
        ) : (
          <TooltipProvider delayDuration={150}>
            <div className="space-y-3">
              {companies.map((company) => (
                <CompanyCoverageRow
                  key={company.company_id}
                  company={company}
                  onCellClick={onCellClick}
                  onImportCompany={onImportCompany}
                />
              ))}
            </div>
          </TooltipProvider>
        )}
      </CardContent>
    </Card>
  );
}
