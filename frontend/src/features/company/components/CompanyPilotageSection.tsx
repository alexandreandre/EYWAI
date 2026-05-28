import { useMemo, useState } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CompanyKPIs } from "@/api/company";
import { KpiCard } from "@/components/analytics/KpiCard";
import { EmptyChartState } from "@/components/analytics/EmptyChartState";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CHART_CONTRACT_COLORS } from "@/lib/analyticsChartColors";
import {
  computePeriodPayroll,
  filterEvolutionForChart,
  percentDelta,
  type PeriodPayrollSnapshot,
} from "@/features/company/lib/companyPeriodKpis";
import type { PeriodSelection } from "@/lib/analyticsPeriod";

const eur = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

function formatMonthLabel(monthStr: string): string {
  const [year, month] = monthStr.split("-");
  const names = ["Jan", "Fév", "Mar", "Avr", "Mai", "Juin", "Juil", "Aoû", "Sep", "Oct", "Nov", "Déc"];
  const idx = parseInt(month, 10) - 1;
  return `${names[idx] ?? month} ${year}`;
}

type CompanyPilotageSectionProps = {
  kpis: CompanyKPIs;
  period: PeriodSelection;
};

export function CompanyPilotageSection({
  kpis,
  period,
}: CompanyPilotageSectionProps): JSX.Element {
  const [evolutionMonths, setEvolutionMonths] = useState<6 | 12 | 24>(12);
  const [jobMetric, setJobMetric] = useState<"count" | "share">("count");

  const payroll = useMemo(
    () => computePeriodPayroll(kpis, period),
    [kpis, period],
  );

  const headcountDelta = useMemo(() => {
    const prev = kpis.total_employees;
    if (prev <= 0) return undefined;
    const hires = kpis.new_hires_last_30_days;
    return percentDelta(kpis.total_employees, Math.max(prev - hires, 1));
  }, [kpis]);

  const evolutionChart = useMemo(() => {
    return filterEvolutionForChart(kpis, evolutionMonths).map((row) => ({
      ...row,
      label: formatMonthLabel(row.month),
    }));
  }, [kpis, evolutionMonths]);

  const contractData = useMemo(() => {
    return Object.entries(kpis.contract_distribution).map(([name, value]) => ({
      name,
      value,
    }));
  }, [kpis.contract_distribution]);

  const jobData = useMemo(() => {
    const entries = Object.entries(kpis.job_distribution)
      .map(([name, count]) => ({
        name: name.length > 28 ? `${name.slice(0, 28)}…` : name,
        fullName: name,
        count,
        share: kpis.total_employees > 0 ? (count / kpis.total_employees) * 100 : 0,
      }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
    return entries;
  }, [kpis.job_distribution, kpis.total_employees]);

  const avgCost =
    kpis.total_employees > 0 ? payroll.totalCost / kpis.total_employees : 0;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard
          label="Effectif actif"
          value={kpis.total_employees}
          hint="collaborateurs"
          delta={
            headcountDelta != null
              ? { value: headcountDelta, worseIfPositive: false }
              : undefined
          }
        />
        <KpiCard
          label="Masse salariale brute"
          value={eur.format(payroll.gross)}
          delta={deltaFromPayroll(payroll.gross, payroll.previousGross, false)}
        />
        <KpiCard
          label="Coût total employeur"
          value={eur.format(payroll.totalCost)}
          delta={deltaFromPayroll(payroll.totalCost, payroll.previousTotalCost, false)}
        />
        <KpiCard
          label="Taux de charges"
          value={`${payroll.payrollTaxRate} %`}
          hint={eur.format(avgCost) + " moy. / salarié"}
          delta={undefined}
        />
      </div>

      <Tabs defaultValue="paie" className="space-y-4">
        <TabsList>
          <TabsTrigger value="effectifs">Effectifs</TabsTrigger>
          <TabsTrigger value="paie">Paie</TabsTrigger>
        </TabsList>

        <TabsContent value="effectifs" className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Répartition des contrats</CardTitle>
                <CardDescription>CDI, CDD et autres types</CardDescription>
              </CardHeader>
              <CardContent className="h-[320px]">
                {contractData.length === 0 ? (
                  <EmptyChartState message="Aucune donnée contrat" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={contractData}
                        dataKey="value"
                        nameKey="name"
                        cx="50%"
                        cy="45%"
                        outerRadius={90}
                        label={({ percent }) => `${(percent * 100).toFixed(0)}%`}
                      >
                        {contractData.map((_, i) => (
                          <Cell
                            key={i}
                            fill={CHART_CONTRACT_COLORS[i % CHART_CONTRACT_COLORS.length]}
                          />
                        ))}
                      </Pie>
                      <Tooltip formatter={(v: number) => [`${v} salarié(s)`, "Effectif"]} />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-2">
                <div>
                  <CardTitle className="text-base">Top 10 postes</CardTitle>
                  <CardDescription>Par effectif</CardDescription>
                </div>
                <ToggleGroup
                  type="single"
                  value={jobMetric}
                  onValueChange={(v) => {
                    if (v === "count" || v === "share") setJobMetric(v);
                  }}
                  className="h-8"
                >
                  <ToggleGroupItem value="count" className="text-xs px-2 h-7">
                    Effectif
                  </ToggleGroupItem>
                  <ToggleGroupItem value="share" className="text-xs px-2 h-7">
                    %
                  </ToggleGroupItem>
                </ToggleGroup>
              </CardHeader>
              <CardContent className="h-[320px]">
                {jobData.length === 0 ? (
                  <EmptyChartState message="Aucun poste renseigné" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={jobData} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                      <XAxis type="number" tickFormatter={(v) => (jobMetric === "share" ? `${v}%` : String(v))} />
                      <YAxis type="category" dataKey="name" width={100} tick={{ fontSize: 11 }} />
                      <Tooltip
                        formatter={(v: number) =>
                          jobMetric === "share" ? [`${v.toFixed(1)}%`, "Part"] : [v, "Effectif"]
                        }
                        labelFormatter={(_, payload) =>
                          payload?.[0]?.payload?.fullName ?? ""
                        }
                      />
                      <Bar
                        dataKey={jobMetric === "share" ? "share" : "count"}
                        fill="hsl(var(--primary))"
                        radius={[0, 4, 4, 0]}
                      />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="paie" className="space-y-4">
          <Card>
            <CardHeader className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <CardTitle className="text-base">Évolution masse salariale & coût employeur</CardTitle>
                <CardDescription>Comparaison sur la période sélectionnée</CardDescription>
              </div>
              <ToggleGroup
                type="single"
                value={String(evolutionMonths)}
                onValueChange={(v) => {
                  const n = Number(v);
                  if (n === 6 || n === 12 || n === 24) setEvolutionMonths(n);
                }}
                className="h-8 w-fit"
              >
                <ToggleGroupItem value="6" className="text-xs px-2 h-7">
                  6 mois
                </ToggleGroupItem>
                <ToggleGroupItem value="12" className="text-xs px-2 h-7">
                  12 mois
                </ToggleGroupItem>
                <ToggleGroupItem value="24" className="text-xs px-2 h-7">
                  24 mois
                </ToggleGroupItem>
              </ToggleGroup>
            </CardHeader>
            <CardContent className="h-[360px]">
              {evolutionChart.length === 0 ? (
                <EmptyChartState message="Aucune donnée de paie sur cette période" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={evolutionChart}>
                    <defs>
                      <linearGradient id="grossGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                        <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="costGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(var(--destructive))" stopOpacity={0.25} />
                        <stop offset="95%" stopColor="hsl(var(--destructive))" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={(v) => eur.format(v)} width={72} tick={{ fontSize: 11 }} />
                    <Tooltip formatter={(v: number) => eur.format(v)} />
                    <Legend />
                    <Area
                      type="monotone"
                      dataKey="masse_salariale_brute"
                      stroke="hsl(var(--primary))"
                      fill="url(#grossGrad)"
                      name="Masse brute"
                    />
                    <Area
                      type="monotone"
                      dataKey="cout_total_employeur"
                      stroke="hsl(var(--destructive))"
                      fill="url(#costGrad)"
                      name="Coût employeur"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>

          <Card className="bg-muted/30">
            <CardHeader>
              <CardTitle className="text-base">Synthèse période</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <div>
                  <p className="text-xs text-muted-foreground">Masse salariale brute</p>
                  <p className="text-xl font-bold text-amber-700 tabular-nums">
                    {eur.format(payroll.gross)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Coût total employeur</p>
                  <p className="text-xl font-bold text-purple-700 tabular-nums">
                    {eur.format(payroll.totalCost)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Nouvelles embauches (30j)</p>
                  <p className="text-xl font-bold text-emerald-700 tabular-nums">
                    +{kpis.new_hires_last_30_days}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

function deltaFromPayroll(
  current: number,
  previous: number,
  worseIfPositive: boolean,
): { value: number; worseIfPositive: boolean } | undefined {
  const d = percentDelta(current, previous);
  if (d == null) return undefined;
  return { value: d, worseIfPositive };
}
