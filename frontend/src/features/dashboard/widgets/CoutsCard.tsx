import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart';
import { PayrollSourceBadge } from '@/components/analytics/PayrollSourceBadge';
import { Bar, BarChart, CartesianGrid, Legend, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts';
import type { ChartDataPoint, KpiData } from '@/features/dashboard/types';
import { formatMonthOverMonthDelta } from '@/features/dashboard/widgets/dashboardFormatters';

const chartConfig = {
  Net_Verse: {
    label: 'Net Versé',
    color: 'hsl(142, 76%, 36%)',
  },
  Charges: {
    label: 'Charges',
    color: 'hsl(0, 80%, 50%)',
  },
} satisfies ChartConfig;

interface CoutsCardProps {
  kpis: KpiData;
  chartData: ChartDataPoint[];
}

export function CoutsCard({ kpis, chartData }: CoutsCardProps) {
  const payroll = kpis.payroll;
  const showEmployerCost = payroll?.source === 'payslip' && payroll.employer_cost > 0;
  const primaryAmount = showEmployerCost ? payroll.employer_cost : payroll?.gross ?? 0;
  const primaryLabel = showEmployerCost ? 'Coût employeur' : 'Masse brute';
  const hasMixedSources = payroll?.has_mixed_sources ?? false;

  let coutDeltaPct: number | null = null;
  let netDeltaPct: number | null = null;
  if (chartData.length >= 2 && payroll?.source !== 'none') {
    const prev = chartData[chartData.length - 2];
    const last = chartData[chartData.length - 1];
    if (prev.source !== 'none' && last.source !== 'none') {
      const prevCout = prev.Net_Verse + prev.Charges;
      const lastCout = last.Net_Verse + last.Charges;
      if (prevCout > 0) {
        coutDeltaPct = ((lastCout - prevCout) / prevCout) * 100;
      }
      if (prev.Net_Verse > 0) {
        netDeltaPct = ((last.Net_Verse - prev.Net_Verse) / prev.Net_Verse) * 100;
      }
    }
  }
  const coutDeltaLabel = formatMonthOverMonthDelta(coutDeltaPct);
  const netDeltaLabel = formatMonthOverMonthDelta(netDeltaPct);

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="text-lg font-semibold">Coûts</CardTitle>
          {payroll ? (
            <PayrollSourceBadge
              source={payroll.source}
              sourceLabel={payroll.source_label}
              partial={payroll.partial}
            />
          ) : null}
        </div>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            {primaryLabel} {kpis.currentMonth}
          </h3>
          {payroll?.source === 'none' ? (
            <p className="text-sm text-muted-foreground">
              Aucune masse disponible pour ce mois. Importez une DSN mensuelle ou générez les
              bulletins dans EYWAI.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div className="text-center">
                <p className="text-xs text-muted-foreground font-medium mb-1">{primaryLabel}</p>
                <div className="text-2xl font-bold text-foreground tabular-nums">
                  {primaryAmount.toLocaleString('fr-FR')} €
                </div>
                {coutDeltaLabel && showEmployerCost ? (
                  <p className="text-xs text-muted-foreground mt-1">{coutDeltaLabel}</p>
                ) : null}
              </div>
              <div className="text-center">
                <p className="text-xs text-muted-foreground font-medium mb-1">
                  {payroll?.source === 'dsn' ? 'Net imposable (DSN)' : 'Net versé'}
                </p>
                <div className="text-2xl font-bold text-foreground tabular-nums">
                  {(payroll?.net ?? kpis.netVerse).toLocaleString('fr-FR')} €
                </div>
                {netDeltaLabel ? (
                  <p className="text-xs text-muted-foreground mt-1">{netDeltaLabel}</p>
                ) : null}
              </div>
            </div>
          )}
        </div>

        <div className="pt-4 border-t">
          <div className="flex flex-wrap items-center justify-between gap-2 mb-4">
            <h3 className="text-sm font-medium text-muted-foreground">Évolution (12 derniers mois)</h3>
            {hasMixedSources ? (
              <span className="text-xs text-muted-foreground">Série mixte bulletins / DSN</span>
            ) : null}
          </div>
          <ChartContainer config={chartConfig} className="h-[250px] w-full">
            <BarChart data={chartData}>
              <CartesianGrid vertical={false} strokeDasharray="3 3" />
              <XAxis
                dataKey="name"
                tickLine={false}
                axisLine={false}
                tickMargin={8}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                tickFormatter={(value) => `${(value / 1000).toFixed(0)}k€`}
              />
              <RechartsTooltip
                content={<ChartTooltipContent />}
                formatter={(value: number) => `${value.toLocaleString('fr-FR')} €`}
              />
              <Legend />
              <Bar
                dataKey="Net_Verse"
                stackId="a"
                fill="var(--color-Net_Verse)"
                radius={[0, 0, 0, 0]}
                name="Net Versé"
              />
              <Bar
                dataKey="Charges"
                stackId="a"
                fill="var(--color-Charges)"
                radius={[4, 4, 0, 0]}
                name="Charges"
              />
            </BarChart>
          </ChartContainer>
        </div>
      </CardContent>
    </Card>
  );
}
