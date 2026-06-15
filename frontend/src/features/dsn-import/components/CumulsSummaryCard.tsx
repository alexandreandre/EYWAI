import { ChevronDown, BarChart3 } from 'lucide-react';
import { formatEuroAmount } from '@/lib/careerFormat';
import { cn } from '@/lib/utils';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

export type CumulsPeriodSummary = {
  period: string;
  employee_count: number;
  employees_with_brut: number;
  employees_without_brut: number;
  brut: number;
  net_imposable: number;
  pas: number;
  heures: number;
  reduction_generale_patronale: number;
  avg_brut: number;
};

export type CumulsSummary = {
  period_count: number;
  employee_count: number;
  entry_count: number;
  by_period: CumulsPeriodSummary[];
  totals: {
    brut: number;
    net_imposable: number;
    pas: number;
    heures: number;
    reduction_generale_patronale: number;
  };
};

type CumulsSummaryCardProps = {
  summary: CumulsSummary;
  formatPeriod: (min?: string | null, max?: string | null) => string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function StatTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2.5">
      <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-0.5 text-sm font-semibold tabular-nums">{value}</p>
    </div>
  );
}

export function CumulsSummaryCard({ summary, formatPeriod, open, onOpenChange }: CumulsSummaryCardProps) {
  const { period_count, employee_count, entry_count, by_period, totals } = summary;
  const subtitle =
    period_count <= 1
      ? `${employee_count} salarié${employee_count > 1 ? 's' : ''} × ${period_count} mois`
      : `${employee_count} salariés × ${period_count} mois (${entry_count} fichiers cumuls)`;

  return (
    <Collapsible open={open} onOpenChange={onOpenChange}>
      <Card>
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center justify-between gap-3 px-6 py-4 text-left hover:bg-muted/30"
          >
            <div className="min-w-0 space-y-0.5">
              <div className="flex flex-wrap items-center gap-2">
                <BarChart3 className="h-4 w-4 shrink-0 text-muted-foreground" />
                <span className="font-semibold">Cumuls de paie</span>
                <Badge variant="secondary" className="font-normal">
                  {period_count} mois
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground">{subtitle}</p>
            </div>
            <div className="flex shrink-0 items-center gap-3">
              <span className="hidden text-sm font-semibold tabular-nums text-foreground sm:inline">
                {formatEuroAmount(totals.brut ?? 0)} brut
              </span>
              <ChevronDown
                className={cn('h-4 w-4 text-muted-foreground transition-transform', open && 'rotate-180')}
              />
            </div>
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <CardContent className="space-y-4 border-t pt-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatTile label="Masse salariale brute" value={formatEuroAmount(totals.brut ?? 0)} />
              <StatTile label="Net imposable" value={formatEuroAmount(totals.net_imposable ?? 0)} />
              <StatTile label="Prélèvement à la source" value={formatEuroAmount(totals.pas ?? 0)} />
              <StatTile
                label="Heures déclarées"
                value={`${(totals.heures ?? 0).toLocaleString('fr-FR', { maximumFractionDigits: 1 })} h`}
              />
            </div>

            <div className="overflow-x-auto rounded-lg border">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Période</TableHead>
                    <TableHead className="text-right">Salariés</TableHead>
                    <TableHead className="text-right">Brut total</TableHead>
                    <TableHead className="hidden text-right md:table-cell">Brut moyen</TableHead>
                    <TableHead className="hidden text-right lg:table-cell">Net imposable</TableHead>
                    <TableHead className="hidden text-right lg:table-cell">PAS</TableHead>
                    <TableHead className="hidden text-right xl:table-cell">Sans brut</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {by_period.map((row) => (
                    <TableRow key={row.period}>
                      <TableCell className="font-medium">{formatPeriod(row.period, row.period)}</TableCell>
                      <TableCell className="text-right tabular-nums">{row.employee_count}</TableCell>
                      <TableCell className="text-right tabular-nums">{formatEuroAmount(row.brut)}</TableCell>
                      <TableCell className="hidden text-right tabular-nums md:table-cell">
                        {formatEuroAmount(row.avg_brut)}
                      </TableCell>
                      <TableCell className="hidden text-right tabular-nums lg:table-cell">
                        {formatEuroAmount(row.net_imposable)}
                      </TableCell>
                      <TableCell className="hidden text-right tabular-nums lg:table-cell">
                        {formatEuroAmount(row.pas)}
                      </TableCell>
                      <TableCell className="hidden text-right tabular-nums xl:table-cell">
                        {row.employees_without_brut > 0 ? (
                          <Badge variant="outline" className="font-normal">
                            {row.employees_without_brut}
                          </Badge>
                        ) : (
                          <span className="text-muted-foreground">0</span>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {by_period.length > 1 && (
                    <TableRow className="bg-muted/30 font-medium">
                      <TableCell>Total période</TableCell>
                      <TableCell className="text-right tabular-nums">{employee_count}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatEuroAmount(totals.brut ?? 0)}
                      </TableCell>
                      <TableCell colSpan={4} />
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>

            <p className="text-xs text-muted-foreground">
              Montants extraits des rubriques DSN du mois (rémunérations, net fiscal, PAS). À
              l&apos;import, un fichier <code className="rounded bg-muted px-1">cumuls/MM.json</code>{' '}
              est généré par salarié et par mois.
            </p>
          </CardContent>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}

export function buildCumulsSummaryFromItems(
  items: Array<{ mapped_payload?: Record<string, unknown> }>,
): CumulsSummary | null {
  if (!items.length) return null;

  const byPeriod = new Map<
    string,
    CumulsPeriodSummary & { _employees: Set<string> }
  >();
  const employees = new Set<string>();

  for (const it of items) {
    const payload = it.mapped_payload ?? {};
    const period = String(payload.period ?? '');
    if (!period) continue;
    const monthTotals = (payload.month_totals ?? {}) as Record<string, number>;
    const empKey = String(payload.employee_key ?? payload.nir ?? '');
    if (empKey) employees.add(empKey);

    let row = byPeriod.get(period);
    if (!row) {
      row = {
        period,
        employee_count: 0,
        employees_with_brut: 0,
        employees_without_brut: 0,
        brut: 0,
        net_imposable: 0,
        pas: 0,
        heures: 0,
        reduction_generale_patronale: 0,
        avg_brut: 0,
        _employees: new Set(),
      };
      byPeriod.set(period, row);
    }

    row.employee_count += 1;
    const brut = Number(monthTotals.brut ?? 0);
    if (brut > 0) row.employees_with_brut += 1;
    else row.employees_without_brut += 1;
    row.brut = Math.round((row.brut + brut) * 100) / 100;
    row.net_imposable = Math.round((row.net_imposable + Number(monthTotals.net_imposable ?? 0)) * 100) / 100;
    row.pas = Math.round((row.pas + Number(monthTotals.pas ?? 0)) * 100) / 100;
    row.heures = Math.round((row.heures + Number(monthTotals.heures ?? 0)) * 100) / 100;
    row.reduction_generale_patronale = Math.round(
      (row.reduction_generale_patronale + Number(monthTotals.reduction_generale_patronale ?? 0)) * 100,
    ) / 100;
  }

  const by_period = Array.from(byPeriod.values())
    .sort((a, b) => a.period.localeCompare(b.period))
    .map(({ _employees: _, ...row }) => ({
      ...row,
      avg_brut: row.employee_count ? Math.round((row.brut / row.employee_count) * 100) / 100 : 0,
    }));

  const totals = by_period.reduce(
    (acc, row) => ({
      brut: acc.brut + row.brut,
      net_imposable: acc.net_imposable + row.net_imposable,
      pas: acc.pas + row.pas,
      heures: acc.heures + row.heures,
      reduction_generale_patronale: acc.reduction_generale_patronale + row.reduction_generale_patronale,
    }),
    { brut: 0, net_imposable: 0, pas: 0, heures: 0, reduction_generale_patronale: 0 },
  );

  return {
    period_count: by_period.length,
    employee_count: employees.size,
    entry_count: items.length,
    by_period,
    totals,
  };
}
