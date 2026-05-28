import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { ChartContainer, ChartTooltipContent, type ChartConfig } from '@/components/ui/chart';
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
  let coutDeltaPct: number | null = null;
  let netDeltaPct: number | null = null;
  if (chartData.length >= 2) {
    const prev = chartData[chartData.length - 2];
    const last = chartData[chartData.length - 1];
    const prevCout = prev.Net_Verse + prev.Charges;
    const lastCout = last.Net_Verse + last.Charges;
    if (prevCout > 0) {
      coutDeltaPct = ((lastCout - prevCout) / prevCout) * 100;
    }
    if (prev.Net_Verse > 0) {
      netDeltaPct = ((last.Net_Verse - prev.Net_Verse) / prev.Net_Verse) * 100;
    }
  }
  const coutDeltaLabel = formatMonthOverMonthDelta(coutDeltaPct);
  const netDeltaLabel = formatMonthOverMonthDelta(netDeltaPct);

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-lg font-semibold">Coûts</CardTitle>
      </CardHeader>
      <CardContent className="space-y-6">
        <div>
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            Masse salariale {kpis.currentMonth}
          </h3>
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
            <div className="text-center">
              <p className="text-xs text-muted-foreground font-medium mb-1">Coût total</p>
              <div className="text-2xl font-bold text-foreground tabular-nums">
                {kpis.coutTotal.toLocaleString('fr-FR')} €
              </div>
              {coutDeltaLabel && (
                <p className="text-xs text-muted-foreground mt-1">{coutDeltaLabel}</p>
              )}
            </div>
            <div className="text-center">
              <p className="text-xs text-muted-foreground font-medium mb-1">Net versé</p>
              <div className="text-2xl font-bold text-foreground tabular-nums">
                {kpis.netVerse.toLocaleString('fr-FR')} €
              </div>
              {netDeltaLabel && (
                <p className="text-xs text-muted-foreground mt-1">{netDeltaLabel}</p>
              )}
            </div>
          </div>
        </div>

        <div className="pt-4 border-t">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">Évolution (12 derniers mois)</h3>
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
