import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart';
import { PayrollSourceBadge } from '@/components/analytics/PayrollSourceBadge';
import { Bar, BarChart, CartesianGrid, Legend, Tooltip as RechartsTooltip, XAxis, YAxis } from 'recharts';
import type { ChartDataPoint, KpiData } from '@/features/dashboard/types';
import {
  resolveChartStackLabels,
  resolvePrimaryPayrollMetric,
} from '@/features/dashboard/lib/chartStackLabels';
import { formatMonthOverMonthDelta } from '@/features/dashboard/widgets/dashboardFormatters';
import { useMemo } from 'react';

interface CoutsCardProps {
  kpis: KpiData;
  chartData: ChartDataPoint[];
}

export function CoutsCard({ kpis, chartData }: CoutsCardProps) {
  const payroll = kpis.payroll;
  const primary = resolvePrimaryPayrollMetric(payroll);
  const chartLabels = useMemo(
    () => resolveChartStackLabels(payroll, chartData),
    [payroll, chartData],
  );

  const chartConfig = useMemo(
    () =>
      ({
        Net_Verse: {
          label: chartLabels.netLabel,
          color: 'hsl(142, 76%, 36%)',
        },
        Charges: {
          label: chartLabels.chargesLabel,
          color: 'hsl(24, 95%, 53%)',
        },
      }) satisfies ChartConfig,
    [chartLabels],
  );

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
  const showPrimaryDelta = primary.label === 'Coût employeur' && coutDeltaLabel;

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
            {primary.label} {kpis.currentMonth}
          </h3>
          {payroll?.source === 'none' ? (
            <p className="text-sm text-muted-foreground">
              Aucune masse disponible pour ce mois. Importez une DSN mensuelle ou générez les
              bulletins dans EYWAI.
            </p>
          ) : (
            <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
              <div className="text-center">
                <p className="text-xs text-muted-foreground font-medium mb-1">{primary.label}</p>
                <div className="text-2xl font-bold text-foreground tabular-nums">
                  {primary.amount.toLocaleString('fr-FR')} €
                </div>
                {showPrimaryDelta ? (
                  <p className="text-xs text-muted-foreground mt-1">{coutDeltaLabel}</p>
                ) : null}
              </div>
              <div className="text-center">
                <p className="text-xs text-muted-foreground font-medium mb-1">
                  {primary.secondaryLabel}
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
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
            <div>
              <h3 className="text-sm font-medium text-muted-foreground">
                Évolution (12 derniers mois)
              </h3>
              {chartLabels.subtitle ? (
                <p className="text-xs text-muted-foreground mt-0.5">{chartLabels.subtitle}</p>
              ) : null}
            </div>
            {payroll?.has_mixed_sources ? (
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
                name={chartLabels.netLabel}
              />
              <Bar
                dataKey="Charges"
                stackId="a"
                fill="var(--color-Charges)"
                radius={[4, 4, 0, 0]}
                name={chartLabels.chargesLabel}
              />
            </BarChart>
          </ChartContainer>
        </div>
      </CardContent>
    </Card>
  );
}
