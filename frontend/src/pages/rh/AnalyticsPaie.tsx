import { RhPageHeader } from '@/components/layout';
import { useCallback, useMemo, useState, type ReactNode } from "react";
import { Link, Navigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Download,
  ExternalLink,
  FileDown,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  XAxis,
  YAxis,
} from "recharts";

import {
  getPayrollAnalyticsBreakdown,
  getPayrollAnalyticsSummary,
  getPayrollAnalyticsTrends,
  getPayrollPeriods,
  type BreakdownGroupBy,
  type CycleStatus,
  type PayrollAnalyticsSummary,
  type PayrollTrendPoint,
} from "@/api/payrollAnalytics";
import { getExportHistory } from "@/api/exports";
import apiClient from "@/api/apiClient";
import { getTeams } from "@/api/teams";
import { AnalyticsPeriodControls } from "@/components/analytics/AnalyticsPeriodControls";
import { PayrollAnomaliesPanel } from "@/components/analytics/PayrollAnomaliesPanel";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { useCompany } from "@/contexts/CompanyContext";
import { usePayrollAnalyticsAccess } from "@/hooks/usePayrollAnalyticsAccess";
import { downloadBlob } from '@/lib/downloadBlob';
import {
  buildPeriodBounds,
  defaultPeriodSelection,
  type PeriodSelection,
} from "@/lib/analyticsPeriod";

const eur = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

type TrendMetric = "brut" | "net" | "cout";

const trendChartConfig = {
  value: { label: "Montant", color: "hsl(var(--primary))" },
  charges: { label: "Charges", color: "hsl(var(--muted-foreground) / 0.5)" },
};

function cycleBadge(status: CycleStatus) {
  if (status === "clos") {
    return { label: "Clos", className: "bg-emerald-600 hover:bg-emerald-600" };
  }
  if (status === "en_cours") {
    return { label: "En cours", className: "bg-amber-600 hover:bg-amber-600" };
  }
  return { label: "Brouillon", className: "bg-slate-500 hover:bg-slate-500" };
}

function DeltaHint({ value }: { value: number | null | undefined }) {
  if (value == null) return <span className="text-muted-foreground text-xs">vs M-1 : —</span>;
  const up = value >= 0;
  const Icon = up ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 text-xs ${up ? "text-amber-700" : "text-emerald-700"}`}>
      <Icon className="h-3 w-3" aria-hidden />
      {up ? "+" : ""}
      {value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} % vs M-1
    </span>
  );
}

function KpiTile({
  label,
  value,
  hint,
  badge,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  badge?: ReactNode;
}) {
  return (
    <Card className="overflow-hidden">
      <CardContent className="flex flex-col gap-1 p-4">
        <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">{label}</p>
        <div className="flex flex-wrap items-end justify-between gap-2">
          <p className="text-2xl font-bold tabular-nums leading-none">{value}</p>
          {badge}
        </div>
        {hint ? <div className="text-muted-foreground text-xs">{hint}</div> : null}
      </CardContent>
    </Card>
  );
}

function exportPayrollCsv(
  companyName: string,
  period: string,
  summary: PayrollAnalyticsSummary | undefined,
  trends: PayrollTrendPoint[],
) {
  const rows: string[][] = [
    ["Rapport Analytics Paie", companyName, period],
    [],
    ["Indicateur", "Valeur"],
  ];
  if (summary) {
    rows.push(
      ["Statut cycle", summary.statut_cycle],
      ["Bulletins validés", `${summary.nb_bulletins_valides}/${summary.nb_bulletins_attendus}`],
      ["Anomalies bloquantes", String(summary.anomalies_bloquantes)],
      ["Anomalies avertissements", String(summary.anomalies_warnings)],
      ["Masse brute", String(summary.masse_brute)],
      ["Coût employeur", String(summary.cout_employeur_total)],
      ["Effectif payé", String(summary.effectif_paye)],
      ["À intégrer (total)", String(summary.items_a_integrer.total)],
    );
  }
  rows.push([], ["Période", "Masse brute", "Net versé", "Coût employeur"]);
  for (const p of trends) {
    rows.push([p.period, String(p.masse_brute), String(p.net_verse), String(p.cout_employeur)]);
  }
  const csv = rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  downloadBlob(blob, `analytics-paie-${period}.csv`);
}

export default function AnalyticsPaie() {
  const { activeCompany } = useCompany();
  const access = usePayrollAnalyticsAccess();
  const companyId = access.companyId;

  const [periodSelection, setPeriodSelection] = useState<PeriodSelection>(() =>
    defaultPeriodSelection(),
  );
  const [selectedTeamIds, setSelectedTeamIds] = useState<string[]>([]);
  const [trendMetric, setTrendMetric] = useState<TrendMetric>("brut");
  const [breakdownGroup, setBreakdownGroup] = useState<BreakdownGroupBy>("team");

  const periodBounds = useMemo(
    () => buildPeriodBounds(periodSelection),
    [periodSelection],
  );
  /** Période API paie (YYYY-MM) — indépendante de exportKey (semaine Sxx, année seule). */
  const apiPeriod = useMemo(
    () =>
      `${periodBounds.payrollYear}-${String(periodBounds.payrollMonth).padStart(2, "0")}`,
    [periodBounds.payrollYear, periodBounds.payrollMonth],
  );
  const periodExportKey = periodBounds.exportKey;
  const payrollYear = periodBounds.payrollYear;
  const payrollMonth = periodBounds.payrollMonth;

  const teamIdsParam = selectedTeamIds.length > 0 ? selectedTeamIds : undefined;

  const { data: teamsData } = useQuery({
    queryKey: ["teams-list", companyId],
    queryFn: () => getTeams(false),
    enabled: Boolean(companyId),
  });

  const {
    data: summary,
    isLoading: summaryLoading,
    isFetching: summaryFetching,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["payroll-analytics-summary", companyId, apiPeriod, teamIdsParam],
    queryFn: () => getPayrollAnalyticsSummary(companyId, apiPeriod, teamIdsParam),
    enabled: Boolean(companyId) && access.canView,
  });

  const {
    data: trends,
    isLoading: trendsLoading,
    refetch: refetchTrends,
  } = useQuery({
    queryKey: ["payroll-analytics-trends", companyId, apiPeriod, teamIdsParam],
    queryFn: () =>
      getPayrollAnalyticsTrends(companyId, {
        months: 12,
        endPeriod: apiPeriod,
        teamIds: teamIdsParam,
      }),
    enabled: Boolean(companyId) && access.canView,
  });

  const {
    data: breakdown,
    isLoading: breakdownLoading,
    refetch: refetchBreakdown,
  } = useQuery({
    queryKey: ["payroll-analytics-breakdown", companyId, apiPeriod, breakdownGroup, teamIdsParam],
    queryFn: () =>
      getPayrollAnalyticsBreakdown(companyId, apiPeriod, breakdownGroup, teamIdsParam),
    enabled: Boolean(companyId) && access.canView,
  });

  const { data: periodsData } = useQuery({
    queryKey: ["payroll-periods", companyId, payrollYear],
    queryFn: () => getPayrollPeriods(companyId, payrollYear),
    enabled: Boolean(companyId) && access.canView,
  });

  const { data: exportHistory } = useQuery({
    queryKey: ["export-history-paie", companyId, apiPeriod],
    queryFn: () => getExportHistory(undefined, apiPeriod),
    enabled: Boolean(companyId) && access.canView,
  });

  const { data: ratesData } = useQuery({
    queryKey: ["rates-all-paie", companyId],
    queryFn: async () => {
      const { data } = await apiClient.get<Record<string, { last_checked_at?: string }>>(
        "/api/rates/all",
      );
      return data;
    },
    enabled: Boolean(companyId) && access.canView,
  });

  const handlePeriodChange = useCallback((next: PeriodSelection) => {
    setPeriodSelection(next);
  }, []);

  const handleRefresh = () => {
    void refetchSummary();
    void refetchTrends();
    void refetchBreakdown();
  };

  const trendChartData = useMemo(() => {
    if (!trends?.points.length) return [];
    return trends.points.map((p) => {
      const label = p.period.slice(5);
      if (trendMetric === "net") {
        return { name: label, value: p.net_verse, period: p.period, is_closed: p.is_closed };
      }
      if (trendMetric === "cout") {
        return { name: label, value: p.cout_employeur, period: p.period, is_closed: p.is_closed };
      }
      return {
        name: label,
        value: p.masse_brute,
        charges: p.cotisations_salariales + p.cotisations_patronales,
        period: p.period,
        is_closed: p.is_closed,
      };
    });
  }, [trends, trendMetric]);

  const breakdownChartData = useMemo(() => {
    if (!breakdown?.items.length) return [];
    return breakdown.items.slice(0, 8).map((it) => ({
      name: it.label.length > 18 ? `${it.label.slice(0, 16)}…` : it.label,
      masse: it.masse_brute,
      fullName: it.label,
    }));
  }, [breakdown]);

  const obsoleteRates = useMemo(() => {
    if (!ratesData) return 0;
    const cutoff = Date.now() - 30 * 86400000;
    let n = 0;
    for (const row of Object.values(ratesData)) {
      const ts = row?.last_checked_at;
      if (!ts) {
        n += 1;
        continue;
      }
      const t = new Date(ts).getTime();
      if (Number.isNaN(t) || t < cutoff) n += 1;
    }
    return n;
  }, [ratesData]);

  const recentExports = useMemo(() => {
    const list = exportHistory?.exports ?? [];
    return list
      .filter((e) =>
        ["journal_paie", "dsn_mensuelle", "od_salaires", "od_globale"].includes(
          String(e.export_type ?? ""),
        ),
      )
      .slice(0, 3);
  }, [exportHistory]);

  const cycleInfo = useMemo(() => {
    const p = periodsData?.periods.find((x) => x.period === apiPeriod);
    return p;
  }, [periodsData, apiPeriod]);

  const anomaliesPeriodHint = useMemo(() => {
    if (periodSelection.granularity === "monthly") return null;
    if (periodSelection.granularity === "weekly") {
      return "Anomalies de paie : mois contenant le début de la semaine sélectionnée.";
    }
    return "Anomalies de paie : dernier mois disponible de l'année (ou mois en cours si année courante).";
  }, [periodSelection.granularity]);

  if (!access.canView) {
    return <Navigate to="/" replace />;
  }

  if (!companyId) {
    return (
      <div className="container max-w-6xl">
        <Alert>
          <AlertTitle>Entreprise requise</AlertTitle>
          <AlertDescription>
            Sélectionnez une entreprise pour afficher Analytics Paie.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const companyName = activeCompany?.company_name ?? "—";
  const periodLabel = periodBounds.label;
  const cycle = summary ? cycleBadge(summary.statut_cycle) : null;
  const showBlockingAlert = (summary?.anomalies_bloquantes ?? 0) > 0;

  return (
    <div className="container max-w-7xl space-y-6">
      <header className="space-y-4">
        <RhPageHeader
          title="Analytics Paie"
          description={`Pilotage paie — ${companyName} — ${periodLabel}${
            cycleInfo?.status === 'closed' && cycleInfo.closed_at
              ? ` — Cycle clos depuis le ${new Date(cycleInfo.closed_at).toLocaleDateString('fr-FR')}`
              : ''
          }`}
          actions={
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                onClick={handleRefresh}
                disabled={summaryFetching}
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${summaryFetching ? 'animate-spin' : ''}`} />
                Actualiser
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="h-9"
                onClick={() =>
                  exportPayrollCsv(companyName, periodExportKey, summary, trends?.points ?? [])
                }
                disabled={!summary}
              >
                <Download className="mr-2 h-4 w-4" />
                Exporter
              </Button>
              {access.canGeneratePayroll ? (
                <Button variant="default" size="sm" className="h-9" asChild>
                  <Link to="/payroll">Générer la paie</Link>
                </Button>
              ) : null}
            </div>
          }
        />

        <AnalyticsPeriodControls
          value={periodSelection}
          onChange={handlePeriodChange}
          periodLabel={periodLabel}
          className="border-t pt-4"
        />

        {teamsData?.teams && teamsData.teams.length > 0 ? (
          <div className="flex flex-wrap items-center gap-3 rounded-lg border bg-muted/20 p-3">
            <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
              Équipes
            </span>
            {teamsData.teams.map((team) => {
              const checked = selectedTeamIds.includes(team.id);
              return (
                <label
                  key={team.id}
                  className="flex cursor-pointer items-center gap-2 text-sm"
                >
                  <Checkbox
                    checked={checked}
                    onCheckedChange={(v) => {
                      setSelectedTeamIds((prev) =>
                        v
                          ? [...prev, team.id]
                          : prev.filter((id) => id !== team.id),
                      );
                    }}
                  />
                  <span
                    className="inline-block h-2 w-2 rounded-full"
                    style={{ backgroundColor: team.color }}
                    aria-hidden
                  />
                  {team.name}
                </label>
              );
            })}
            {selectedTeamIds.length > 0 ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                onClick={() => setSelectedTeamIds([])}
              >
                Tout afficher
              </Button>
            ) : null}
          </div>
        ) : null}
      </header>

      {showBlockingAlert ? (
        <Alert variant="destructive" id="alertes-paie">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>
            {summary!.anomalies_bloquantes} anomalie
            {summary!.anomalies_bloquantes > 1 ? "s" : ""} bloquante
            {summary!.anomalies_bloquantes > 1 ? "s" : ""} — {periodLabel}
          </AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>
              Des bulletins nécessitent une correction avant validation de la paie.
              {summary!.anomalies_warnings > 0
                ? ` ${summary!.anomalies_warnings} avertissement(s) en plus.`
                : ""}
            </span>
            <Button variant="outline" size="sm" className="h-8 border-destructive/40" asChild>
              <a href="#anomalies-paie">Voir le détail</a>
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {/* Zone 2 — KPI */}
      <section aria-label="Indicateurs du cycle de paie">
        {summaryLoading && !summary ? (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-lg" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <KpiTile
              label="Statut du cycle"
              value={
                cycle ? (
                  <Badge className={cycle.className}>{cycle.label}</Badge>
                ) : (
                  "—"
                )
              }
              hint={
                summary
                  ? `${summary.nb_bulletins_valides} / ${summary.nb_bulletins_attendus} bulletins validés`
                  : undefined
              }
            />
            <KpiTile
              label="Anomalies"
              value={summary ? summary.anomalies_bloquantes + summary.anomalies_warnings : "—"}
              hint={
                summary ? (
                  <a href="#anomalies-paie" className="text-primary hover:underline">
                    {summary.anomalies_bloquantes} bloquante(s)
                  </a>
                ) : undefined
              }
            />
            <KpiTile
              label="Masse brute"
              value={summary ? eur.format(summary.masse_brute) : "—"}
              hint={<DeltaHint value={summary?.delta_brut_m1_pct} />}
            />
            <KpiTile
              label="Coût employeur"
              value={summary ? eur.format(summary.cout_employeur_total) : "—"}
              hint={<DeltaHint value={summary?.delta_cout_m1_pct} />}
            />
            <KpiTile
              label="Effectif payé"
              value={summary ? summary.effectif_paye : "—"}
              hint={
                summary
                  ? `/ ${summary.effectif_actif} actifs`
                  : undefined
              }
            />
            <KpiTile
              label="À intégrer"
              value={summary ? summary.items_a_integrer.total : "—"}
              hint={
                summary ? (
                  <a href="#a-integrer" className="text-primary hover:underline">
                    Voir le détail
                  </a>
                ) : undefined
              }
            />
          </div>
        )}
      </section>

      {/* Zone 3 — Masse */}
      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3" aria-label="Masse salariale">
        <Card className="lg:col-span-2">
          <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2 p-4 pb-2">
            <div>
              <CardTitle className="text-base">Évolution sur 12 mois</CardTitle>
              <CardDescription>Masse salariale et charges (bulletins validés)</CardDescription>
            </div>
            <ToggleGroup
              type="single"
              value={trendMetric}
              onValueChange={(v) => v && setTrendMetric(v as TrendMetric)}
              className="h-8"
            >
              <ToggleGroupItem value="brut" className="h-8 px-2 text-xs">
                Brut
              </ToggleGroupItem>
              <ToggleGroupItem value="net" className="h-8 px-2 text-xs">
                Net
              </ToggleGroupItem>
              <ToggleGroupItem value="cout" className="h-8 px-2 text-xs">
                Coût employeur
              </ToggleGroupItem>
            </ToggleGroup>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            {trendsLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : trendChartData.length > 0 ? (
              <ChartContainer config={trendChartConfig} className="h-[250px] w-full">
                <BarChart data={trendChartData}>
                  <CartesianGrid vertical={false} strokeDasharray="3 3" />
                  <XAxis dataKey="name" tickLine={false} axisLine={false} />
                  <YAxis tickLine={false} axisLine={false} tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  {trendMetric === "brut" ? (
                    <>
                      <Bar dataKey="value" stackId="a" fill="var(--color-value)" radius={[0, 0, 0, 0]} />
                      <Bar dataKey="charges" stackId="a" fill="var(--color-charges)" radius={[4, 4, 0, 0]} />
                    </>
                  ) : (
                    <Bar dataKey="value" fill="var(--color-value)" radius={[4, 4, 0, 0]}>
                      {trendChartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={
                            entry.is_closed
                              ? "var(--color-value)"
                              : "hsl(var(--primary) / 0.45)"
                          }
                        />
                      ))}
                    </Bar>
                  )}
                </BarChart>
              </ChartContainer>
            ) : (
              <div className="flex h-[220px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 text-center">
                <BarChart3 className="text-muted-foreground h-8 w-8" aria-hidden />
                <p className="text-sm font-medium">Pas encore de bulletins validés</p>
                <p className="text-muted-foreground max-w-xs text-xs">
                  Les courbes apparaîtront après validation des bulletins sur la période.
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="space-y-2 p-4 pb-2">
            <CardTitle className="text-base">Répartition</CardTitle>
            <ToggleGroup
              type="single"
              value={breakdownGroup}
              onValueChange={(v) => v && setBreakdownGroup(v as BreakdownGroupBy)}
              className="h-8 justify-start"
            >
              <ToggleGroupItem value="team" className="h-7 px-2 text-xs">
                Équipe
              </ToggleGroupItem>
              <ToggleGroupItem value="service" className="h-7 px-2 text-xs">
                Service
              </ToggleGroupItem>
              <ToggleGroupItem value="contract_type" className="h-7 px-2 text-xs">
                Contrat
              </ToggleGroupItem>
            </ToggleGroup>
          </CardHeader>
          <CardContent className="p-4 pt-0">
            {breakdownLoading ? (
              <Skeleton className="h-[250px] w-full" />
            ) : breakdownChartData.length > 0 ? (
              <ChartContainer config={{ masse: { label: "Brut", color: "hsl(var(--primary))" } }} className="h-[250px] w-full">
                <BarChart data={breakdownChartData} layout="vertical" margin={{ left: 4, right: 8 }}>
                  <CartesianGrid horizontal={false} strokeDasharray="3 3" />
                  <XAxis type="number" tickFormatter={(v) => `${Math.round(v / 1000)}k`} />
                  <YAxis type="category" dataKey="name" width={72} tickLine={false} />
                  <ChartTooltip content={<ChartTooltipContent />} />
                  <Bar dataKey="masse" fill="var(--color-masse)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ChartContainer>
            ) : (
              <p className="text-muted-foreground py-8 text-center text-sm">
                Aucune donnée de répartition pour {periodLabel}.
              </p>
            )}
            <Button variant="link" size="sm" className="mt-2 h-auto p-0" asChild>
              <Link to="/analytics">
                Voir le détail dans Analytics Team
                <ExternalLink className="ml-1 h-3 w-3" />
              </Link>
            </Button>
          </CardContent>
        </Card>
      </section>

      <PayrollAnomaliesPanel
        companyId={companyId}
        payrollYear={payrollYear}
        payrollMonth={payrollMonth}
        periodLabel={periodLabel}
        periodHint={anomaliesPeriodHint}
      />

      {/* Zone 5 */}
      <section id="a-integrer" aria-label="Éléments à intégrer">
        <h2 className="mb-3 text-lg font-semibold tracking-tight">À intégrer dans la prochaine paie</h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            {
              label: "Notes de frais",
              count: summary?.items_a_integrer.ndf ?? 0,
              href: "/expenses",
            },
            {
              label: "Absences",
              count: summary?.items_a_integrer.absences ?? 0,
              href: "/leaves",
            },
            {
              label: "Primes / saisies",
              count: summary?.items_a_integrer.primes ?? 0,
              href: "/saisies",
            },
            {
              label: "Avances",
              count: summary?.items_a_integrer.avances ?? 0,
              href: "/salary-advances",
            },
          ].map((card) => (
            <Link key={card.href} to={card.href} className="block">
              <Card className="transition-colors hover:bg-muted/40">
                <CardContent className="p-4">
                  <p className="text-2xl font-bold tabular-nums">{card.count}</p>
                  <p className="text-muted-foreground text-sm">{card.label}</p>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      {/* Zone 6 */}
      <Collapsible defaultOpen={obsoleteRates > 0 || recentExports.length > 0}>
        <CollapsibleTrigger asChild>
          <Button variant="ghost" className="w-full justify-between px-0 hover:bg-transparent">
            <span className="text-lg font-semibold tracking-tight">Conformité et exports</span>
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
          </Button>
        </CollapsibleTrigger>
        <CollapsibleContent className="space-y-3 pt-2">
          {obsoleteRates === 0 && recentExports.length === 0 ? (
            <p className="text-muted-foreground text-sm">Tout est à jour pour {periodLabel}.</p>
          ) : null}
          {obsoleteRates > 0 ? (
            <Alert>
              <AlertTitle>Référentiel taux</AlertTitle>
              <AlertDescription className="flex flex-wrap items-center gap-2">
                <span>
                  {obsoleteRates} taux non vérifié(s) depuis plus de 30 jours.
                </span>
                <Button variant="outline" size="sm" className="h-8" asChild>
                  <Link to="/rates">Suivi des taux</Link>
                </Button>
              </AlertDescription>
            </Alert>
          ) : null}
          {recentExports.length > 0 ? (
            <Card>
              <CardHeader className="p-4 pb-2">
                <CardTitle className="text-base flex items-center gap-2">
                  <FileDown className="h-4 w-4" />
                  Derniers exports ({apiPeriod})
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 p-4 pt-0 text-sm">
                {recentExports.map((ex) => (
                  <div
                    key={ex.id}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-md border px-3 py-2"
                  >
                    <span className="font-medium">{ex.export_type}</span>
                    <span className="text-muted-foreground text-xs">
                      {ex.generated_at
                        ? new Date(ex.generated_at).toLocaleString("fr-FR")
                        : "—"}
                    </span>
                  </div>
                ))}
                <Button variant="link" size="sm" className="h-auto p-0" asChild>
                  <Link to="/exports">Tous les exports</Link>
                </Button>
              </CardContent>
            </Card>
          ) : null}
        </CollapsibleContent>
      </Collapsible>
    </div>
  );
}
