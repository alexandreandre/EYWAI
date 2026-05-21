import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BarChart3,
  Calendar,
  ChevronDown,
  Download,
  ExternalLink,
  RefreshCw,
  Users,
} from "lucide-react";

import {
  ACTIONS_LABELS,
  getAnalyticsAvances,
  getAnomaliesPayslips,
  getAuditLogs,
  type AnalyticsAvances,
  type AuditLogEntry,
} from "@/api/analytics";
import { useCompany } from "@/contexts/CompanyContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { AnalyticsPeriodControls } from "@/components/analytics/AnalyticsPeriodControls";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  buildPeriodBounds,
  defaultPeriodSelection,
  type PeriodSelection,
} from "@/lib/analyticsPeriod";

const CHART_PYRAMID_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--primary) / 0.88)",
  "hsl(var(--primary) / 0.76)",
  "hsl(var(--primary) / 0.64)",
  "hsl(var(--primary) / 0.52)",
  "hsl(var(--primary) / 0.4)",
];

const CHART_CONTRACT_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--primary) / 0.75)",
  "hsl(var(--primary) / 0.55)",
  "hsl(var(--primary) / 0.4)",
  "hsl(var(--muted-foreground) / 0.5)",
];

const ABSENCE_COLORS = {
  maladie: "hsl(var(--primary))",
  at: "hsl(var(--primary) / 0.6)",
  autres: "hsl(var(--muted-foreground) / 0.45)",
};

const eur = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

function turnoverBadge(taux: number): { label: string; className: string } {
  if (taux <= 5) {
    return { label: "Faible", className: "bg-emerald-600 hover:bg-emerald-600" };
  }
  if (taux <= 15) {
    return { label: "Modéré", className: "bg-amber-600 hover:bg-amber-600" };
  }
  return { label: "Élevé", className: "bg-red-600 hover:bg-red-600" };
}

function SectionSkeleton(): JSX.Element {
  return (
    <Card>
      <CardHeader className="p-4 pb-2">
        <Skeleton className="h-5 w-48" />
        <Skeleton className="mt-1 h-3 w-full max-w-md" />
      </CardHeader>
      <CardContent className="space-y-2 p-4 pt-0">
        <Skeleton className="h-[220px] w-full" />
      </CardContent>
    </Card>
  );
}

function SectionHeading({
  title,
  subtitle,
  right,
}: {
  title: string;
  subtitle?: string;
  right?: ReactNode;
}): JSX.Element {
  return (
    <div className="mb-3 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <h2 className="text-lg font-semibold leading-tight tracking-tight">{title}</h2>
        {subtitle ? (
          <p className="text-muted-foreground line-clamp-2 text-sm">{subtitle}</p>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

function EmptyChartState({
  icon: Icon,
  title,
  description,
}: {
  icon: typeof BarChart3;
  title: string;
  description: string;
}): JSX.Element {
  return (
    <div
      className="flex h-[220px] flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 px-4 text-center"
      role="status"
    >
      <Icon className="text-muted-foreground h-8 w-8" aria-hidden />
      <p className="text-sm font-medium">{title}</p>
      <p className="text-muted-foreground max-w-xs text-xs">{description}</p>
    </div>
  );
}

function KpiCard({
  label,
  value,
  hint,
  badge,
  delta,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
  badge?: ReactNode;
  delta?: { value: number; worseIfPositive: boolean };
}): JSX.Element {
  const evoNeutral = delta != null && Math.abs(delta.value) < 0.05;
  const evoWorse =
    delta != null && !evoNeutral && (delta.worseIfPositive ? delta.value > 0 : delta.value < 0);

  return (
    <Card className="overflow-hidden">
      <CardContent className="flex flex-col gap-1 p-4">
        <p className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
          {label}
        </p>
        <div className="flex flex-wrap items-end justify-between gap-2">
          <p className="text-2xl font-bold tabular-nums leading-none">{value}</p>
          {badge}
        </div>
        {hint ? <p className="text-muted-foreground text-xs">{hint}</p> : null}
        {delta != null ? (
          <div
            className={`flex items-center gap-1 text-xs font-medium ${
              evoNeutral
                ? "text-muted-foreground"
                : evoWorse
                  ? "text-red-600"
                  : "text-emerald-600"
            }`}
          >
            {!evoNeutral ? (
              delta.value > 0 ? (
                <ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
              ) : (
                <ArrowDownRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
              )
            ) : null}
            <span>
              {delta.value > 0 ? "+" : ""}
              {delta.value.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}% vs période préc.
            </span>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function exportAnalyticsCsv(
  companyName: string,
  period: string,
  data: AnalyticsAvances | undefined,
  anomaliesCount: { bloquants: number; avertissements: number },
): void {
  const rows: string[][] = [
    ["Rapport Analytics Team", companyName, period],
    [],
    ["Indicateur", "Valeur"],
  ];
  if (data) {
    rows.push(
      ["Effectif actif", String(data.effectif_actif)],
      [
        "Turnover annuel (%)",
        data.turnover.taux_turnover_annuel.toLocaleString("fr-FR", { maximumFractionDigits: 1 }),
      ],
      ["Embauches 12 mois", String(data.turnover.nb_embauches_12_mois)],
      ["Départs 12 mois", String(data.turnover.nb_departs_12_mois)],
      [
        "Absentéisme 30j (%)",
        data.absenteisme.taux_global.toLocaleString("fr-FR", { maximumFractionDigits: 2 }),
      ],
      ["Masse salariale brute", String(data.masse_salariale_brute_totale)],
      ["Âge moyen", String(data.age_moyen)],
      ["Ancienneté moyenne (ans)", String(data.anciennete_moyenne_annees)],
    );
  }
  rows.push(
    [],
    ["Anomalies paie bloquantes", String(anomaliesCount.bloquants)],
    ["Anomalies paie avertissements", String(anomaliesCount.avertissements)],
  );
  const csv = rows.map((r) => r.map((c) => `"${c.replace(/"/g, '""')}"`).join(",")).join("\n");
  const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `analytics-team-${period}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export default function Analytics(): JSX.Element {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;

  const [periodSelection, setPeriodSelection] = useState<PeriodSelection>(() =>
    defaultPeriodSelection(),
  );
  const periodBounds = useMemo(
    () => buildPeriodBounds(periodSelection),
    [periodSelection],
  );
  const payrollYear = periodBounds.payrollYear;
  const payrollMonth = periodBounds.payrollMonth;

  const [auditResourceType, setAuditResourceType] = useState<string>("");
  const [auditSince, setAuditSince] = useState(periodBounds.start);
  const [auditUntil, setAuditUntil] = useState(periodBounds.end);
  const [auditLimit, setAuditLimit] = useState(50);
  const [auditOpen, setAuditOpen] = useState(false);

  const handlePeriodChange = useCallback((next: PeriodSelection) => {
    setPeriodSelection(next);
    const bounds = buildPeriodBounds(next);
    setAuditSince(bounds.start);
    setAuditUntil(bounds.end);
    setAuditLimit(50);
  }, []);

  useEffect(() => {
    setAuditLimit(50);
  }, [companyId, auditResourceType, auditSince, auditUntil]);

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["dashboard-analytics", companyId],
    queryFn: () => getAnalyticsAvances(companyId),
    enabled: Boolean(companyId),
  });

  const {
    data: anomaliesData,
    isLoading: anomaliesLoading,
    isFetching: anomaliesFetching,
    error: anomaliesError,
    refetch: refetchAnomalies,
  } = useQuery({
    queryKey: ["payslips-anomalies", companyId, periodBounds.exportKey],
    queryFn: () => getAnomaliesPayslips(companyId, payrollYear, payrollMonth),
    enabled: Boolean(companyId),
    staleTime: 0,
    placeholderData: (previous) => previous,
  });

  const {
    data: auditData,
    isLoading: auditLoading,
    isFetching: auditFetching,
    error: auditError,
    refetch: refetchAudit,
  } = useQuery({
    queryKey: [
      "audit-logs",
      companyId,
      auditResourceType,
      auditSince,
      auditUntil,
      auditLimit,
    ],
    queryFn: () =>
      getAuditLogs(companyId, {
        resource_type: auditResourceType || undefined,
        created_after: auditSince || undefined,
        created_before: auditUntil || undefined,
        limit: auditLimit,
        offset: 0,
      }),
    enabled: Boolean(companyId) && auditOpen,
  });

  const anomaliesSummary = useMemo(() => {
    if (!anomaliesData) {
      return { bloquants: 0, avertissements: 0 };
    }
    let b = 0;
    let a = 0;
    for (const x of anomaliesData.anomalies) {
      if (x.severite === "bloquant") b += 1;
      else a += 1;
    }
    return { bloquants: b, avertissements: a };
  }, [anomaliesData]);

  const insufficient = useMemo(() => {
    if (!data) return false;
    const totalAge = data.pyramide_ages.reduce((s, p) => s + p.count, 0);
    const emb = data.turnover.nb_embauches_12_mois;
    const dep = data.turnover.nb_departs_12_mois;
    return totalAge === 0 && emb === 0 && dep === 0;
  }, [data]);

  const serviceChartData = useMemo(() => {
    if (!data?.effectif_par_service?.length) return [];
    return data.effectif_par_service.map((row) => ({
      service: String(row.service ?? "—"),
      count: Number(row.count ?? 0),
    }));
  }, [data]);

  const contractChartData = useMemo(() => {
    if (!data?.effectif_par_contrat?.length) return [];
    return data.effectif_par_contrat.map((row) => ({
      type: String(row.type ?? "—"),
      count: Number(row.count ?? 0),
    }));
  }, [data]);

  const masseChartData = useMemo(() => {
    if (!data?.masse_salariale_par_service?.length) return [];
    return data.masse_salariale_par_service.map((row) => ({
      service: String(row.service ?? "—"),
      masse: Number(row.masse_salariale_brute ?? 0),
    }));
  }, [data]);

  const turnoverRatioBar = useMemo(() => {
    if (!data) return [];
    const e = data.turnover.nb_embauches_12_mois;
    const d = data.turnover.nb_departs_12_mois;
    return [
      { label: "Embauches (12 mois)", value: e, fill: "hsl(var(--primary))" },
      { label: "Départs (12 mois)", value: d, fill: "hsl(var(--muted-foreground) / 0.45)" },
    ];
  }, [data]);

  const absenceDonutData = useMemo(() => {
    if (!data || data.absenteisme.jours_perdus_total <= 0) return [];
    return [
      {
        name: "Maladie",
        value: data.absenteisme.jours_perdus_maladie,
        fill: ABSENCE_COLORS.maladie,
      },
      {
        name: "AT",
        value: data.absenteisme.jours_perdus_at,
        fill: ABSENCE_COLORS.at,
      },
      {
        name: "Autres",
        value: data.absenteisme.jours_perdus_autres,
        fill: ABSENCE_COLORS.autres,
      },
    ].filter((d) => d.value > 0);
  }, [data]);

  const periodLabel = periodBounds.label;

  const anomaliesPeriodHint = useMemo(() => {
    if (periodSelection.granularity === "monthly") return null;
    if (periodSelection.granularity === "weekly") {
      return "Anomalies de paie : mois contenant le début de la semaine sélectionnée.";
    }
    return "Anomalies de paie : dernier mois disponible de l'année (ou mois en cours si année courante).";
  }, [periodSelection.granularity]);

  if (!companyId) {
    return (
      <div className="container max-w-6xl py-8">
        <Alert>
          <AlertTitle>Entreprise requise</AlertTitle>
          <AlertDescription>
            Sélectionnez une entreprise pour afficher Analytics Team.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const showInitialSkeleton = isLoading && !data;
  const evo = data?.absenteisme.evolution_vs_mois_precedent ?? 0;
  const turnoverB = data ? turnoverBadge(data.turnover.taux_turnover_annuel) : null;

  const handleRefresh = () => {
    void refetch();
    void refetchAnomalies();
    if (auditOpen) void refetchAudit();
  };

  return (
    <div className="container max-w-7xl space-y-6 py-6">
      {/* Header */}
      <header className="space-y-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h1 className="text-2xl font-semibold tracking-tight">Analytics Team</h1>
            <p className="text-muted-foreground text-sm">
              Pilotage des équipes, effectifs et santé organisationnelle —{" "}
              {activeCompany?.company_name ?? "—"}
            </p>
          </div>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9"
              onClick={handleRefresh}
              disabled={isFetching}
            >
              <RefreshCw
                className={`mr-2 h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
              />
              Actualiser
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-9"
              disabled={!data}
              onClick={() =>
                exportAnalyticsCsv(
                  activeCompany?.company_name ?? "entreprise",
                  periodBounds.exportKey,
                  data,
                  anomaliesSummary,
                )
              }
            >
              <Download className="mr-2 h-4 w-4" />
              Exporter
            </Button>
          </div>
        </div>

        <AnalyticsPeriodControls
          value={periodSelection}
          onChange={handlePeriodChange}
          periodLabel={periodLabel}
          hint={
            periodSelection.granularity !== "monthly"
              ? "Indicateurs globaux : 12 mois / 30 jours glissants"
              : null
          }
          className="border-t pt-4"
        />
      </header>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>Erreur</AlertTitle>
          <AlertDescription>
            {error instanceof Error ? error.message : "Chargement impossible."}
          </AlertDescription>
        </Alert>
      ) : null}

      {insufficient && data ? (
        <Alert>
          <AlertTitle>Données partielles</AlertTitle>
          <AlertDescription>
            Peu de mouvements ou d&apos;effectifs renseignés : certains graphiques peuvent rester
            vides. Complétez les fiches salariés (date de naissance, service, contrat).
          </AlertDescription>
        </Alert>
      ) : null}

      {/* KPI strip */}
      {showInitialSkeleton ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      ) : data ? (
        <div
          className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6"
          aria-label="Indicateurs clés"
        >
          <KpiCard
            label="Effectif actif"
            value={data.effectif_actif}
            hint="salariés en poste"
          />
          <KpiCard
            label="Turnover annuel"
            value={`${data.turnover.taux_turnover_annuel.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`}
            badge={
              turnoverB ? (
                <Badge className={turnoverB.className} variant="default">
                  {turnoverB.label}
                </Badge>
              ) : null
            }
            hint={`${data.turnover.nb_embauches_12_mois} emb. · ${data.turnover.nb_departs_12_mois} dép.`}
          />
          <KpiCard
            label="Absentéisme 30j"
            value={`${data.absenteisme.taux_global.toLocaleString("fr-FR", { maximumFractionDigits: 2 })} %`}
            delta={{ value: evo, worseIfPositive: true }}
            hint={`${data.absenteisme.jours_perdus_total} jours perdus`}
          />
          <KpiCard
            label="Masse salariale"
            value={eur.format(data.masse_salariale_brute_totale)}
            hint="brut mensuel de base"
          />
          <KpiCard
            label="Âge moyen"
            value={
              data.age_moyen > 0
                ? `${data.age_moyen.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ans`
                : "—"
            }
            hint="salariés avec date de naissance"
          />
          <KpiCard
            label="Ancienneté moyenne"
            value={
              data.anciennete_moyenne_annees > 0
                ? `${data.anciennete_moyenne_annees.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} ans`
                : "—"
            }
            hint="depuis la date d'embauche"
          />
        </div>
      ) : null}

      {/* Alert banner */}
      {!anomaliesLoading && anomaliesSummary.bloquants > 0 ? (
        <Alert variant="destructive" id="alertes-paie">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>
            {anomaliesSummary.bloquants} anomalie
            {anomaliesSummary.bloquants > 1 ? "s" : ""} bloquante
            {anomaliesSummary.bloquants > 1 ? "s" : ""} — {periodLabel}
          </AlertTitle>
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>
              Des bulletins nécessitent une correction avant validation de la paie.
              {anomaliesSummary.avertissements > 0
                ? ` ${anomaliesSummary.avertissements} avertissement(s) en plus.`
                : ""}
            </span>
            <Button variant="outline" size="sm" className="h-8 border-destructive/40" asChild>
              <a href="#anomalies-paie">Voir le détail</a>
            </Button>
          </AlertDescription>
        </Alert>
      ) : null}

      {showInitialSkeleton ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SectionSkeleton />
            <SectionSkeleton />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SectionSkeleton />
            <SectionSkeleton />
          </div>
          <SectionSkeleton />
          <SectionSkeleton />
        </div>
      ) : (
        <>
          {/* Section 1 — Démographie */}
          <section aria-labelledby="section-demographie">
            <SectionHeading
              title="Démographie"
              subtitle="Structure des équipes : âge et types de contrats des collaborateurs actifs"
            />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Pyramide des âges</CardTitle>
                  <CardDescription>Salariés actifs avec date de naissance</CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  {data && data.pyramide_ages.some((p) => p.count > 0) ? (
                    <div className="h-[240px] w-full min-w-0" aria-label="Pyramide des âges">
                      <ResponsiveContainer width="100%" height={240}>
                        <BarChart
                          data={data.pyramide_ages}
                          layout="vertical"
                          margin={{ left: 4, right: 8, top: 4, bottom: 4 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                          <YAxis
                            type="category"
                            dataKey="tranche"
                            width={48}
                            tick={{ fontSize: 10 }}
                          />
                          <RechartsTooltip
                            formatter={(v: number, _n, ctx) => {
                              const p = ctx?.payload as
                                | AnalyticsAvances["pyramide_ages"][number]
                                | undefined;
                              const pct = p?.pourcentage ?? 0;
                              return [`${v} (${pct}%)`, "Effectif"];
                            }}
                          />
                          <Bar dataKey="count" radius={[0, 4, 4, 0]}>
                            {data.pyramide_ages.map((_, i) => (
                              <Cell
                                key={data.pyramide_ages[i].tranche}
                                fill={CHART_PYRAMID_COLORS[i % CHART_PYRAMID_COLORS.length]}
                              />
                            ))}
                          </Bar>
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartState
                      icon={Users}
                      title="Pyramide non disponible"
                      description="Renseignez les dates de naissance sur les fiches salariés actifs."
                    />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Répartition par contrat</CardTitle>
                  <CardDescription>CDI, CDD et autres types en vigueur</CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  {data && contractChartData.length > 0 ? (
                    <div className="h-[240px] w-full min-w-0" aria-label="Répartition par contrat">
                      <ResponsiveContainer width="100%" height={240}>
                        <PieChart>
                          <Pie
                            data={contractChartData}
                            dataKey="count"
                            nameKey="type"
                            cx="50%"
                            cy="50%"
                            innerRadius={52}
                            outerRadius={80}
                            paddingAngle={2}
                          >
                            {contractChartData.map((_, i) => (
                              <Cell
                                key={contractChartData[i].type}
                                fill={
                                  CHART_CONTRACT_COLORS[i % CHART_CONTRACT_COLORS.length]
                                }
                              />
                            ))}
                          </Pie>
                          <RechartsTooltip
                            formatter={(v: number, name: string) => [v, name]}
                          />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartState
                      icon={BarChart3}
                      title="Aucun contrat renseigné"
                      description="Complétez le type de contrat sur les fiches salariés."
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          </section>

          {/* Section 2 — Mouvements */}
          <section aria-labelledby="section-mouvements" className="mt-6">
            <SectionHeading
              title="Mouvements"
              subtitle="Turnover et effectifs par équipe / service (12 mois glissants)"
            />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Turnover</CardTitle>
                  <CardDescription>
                    Taux annuel sur effectif actuel — embauches et départs
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-4 pt-2">
                  {data ? (
                    <>
                      <div className="flex flex-wrap items-end justify-between gap-2">
                        <div>
                          <p className="text-muted-foreground text-xs">Taux annuel</p>
                          <p className="text-3xl font-bold tabular-nums">
                            {data.turnover.taux_turnover_annuel.toLocaleString("fr-FR", {
                              maximumFractionDigits: 1,
                            })}
                            %
                          </p>
                        </div>
                        {turnoverB ? (
                          <Badge className={turnoverB.className}>{turnoverB.label}</Badge>
                        ) : null}
                      </div>
                      <div className="text-muted-foreground grid grid-cols-2 gap-2 text-sm">
                        <div>
                          Embauches :{" "}
                          <span className="text-foreground font-semibold">
                            {data.turnover.nb_embauches_12_mois}
                          </span>
                        </div>
                        <div>
                          Départs :{" "}
                          <span className="text-foreground font-semibold">
                            {data.turnover.nb_departs_12_mois}
                          </span>
                        </div>
                      </div>
                      <div className="h-[200px] w-full min-w-0" aria-label="Embauches et départs">
                        <ResponsiveContainer width="100%" height={200}>
                          <BarChart
                            data={turnoverRatioBar}
                            layout="vertical"
                            margin={{ left: 4, right: 8, top: 4, bottom: 4 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                            <YAxis
                              type="category"
                              dataKey="label"
                              width={130}
                              tick={{ fontSize: 10 }}
                            />
                            <RechartsTooltip formatter={(v: number) => [v, ""]} />
                            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                              {turnoverRatioBar.map((row) => (
                                <Cell key={row.label} fill={row.fill} />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </>
                  ) : null}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Effectif par service</CardTitle>
                  <CardDescription>Collaborateurs actifs par équipe ou département</CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  {data && serviceChartData.length > 0 ? (
                    <div className="h-[280px] w-full min-w-0" aria-label="Effectif par service">
                      <ResponsiveContainer width="100%" height={280}>
                        <BarChart
                          data={serviceChartData}
                          margin={{ bottom: 56, left: 4, right: 8, top: 4 }}
                        >
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis
                            dataKey="service"
                            angle={-35}
                            textAnchor="end"
                            height={64}
                            interval={0}
                            tick={{ fontSize: 9 }}
                          />
                          <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={32} />
                          <RechartsTooltip />
                          <Bar
                            dataKey="count"
                            fill="hsl(var(--primary))"
                            radius={[4, 4, 0, 0]}
                            name="Effectif"
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartState
                      icon={Users}
                      title="Aucun service assigné"
                      description="Associez chaque salarié à un service pour visualiser la répartition."
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          </section>

          {/* Section 3 — Absentéisme */}
          <section aria-labelledby="section-absenteisme" className="mt-6">
            <SectionHeading
              title="Absentéisme"
              subtitle="30 jours glissants — répartition par motif"
            />
            <Card>
              <CardContent className="space-y-4 p-4">
                {data ? (
                  <>
                    <div className="flex flex-wrap items-end justify-between gap-4">
                      <div>
                        <p className="text-muted-foreground text-xs">Taux global</p>
                        <p className="text-3xl font-bold tabular-nums">
                          {data.absenteisme.taux_global.toLocaleString("fr-FR", {
                            maximumFractionDigits: 2,
                          })}
                          %
                        </p>
                      </div>
                      <div
                        className={`flex items-center gap-1 text-sm font-medium ${
                          Math.abs(evo) < 0.05
                            ? "text-muted-foreground"
                            : evo > 0
                              ? "text-red-600"
                              : "text-emerald-600"
                        }`}
                      >
                        {Math.abs(evo) >= 0.05 ? (
                          evo > 0 ? (
                            <ArrowUpRight className="h-4 w-4" aria-hidden />
                          ) : (
                            <ArrowDownRight className="h-4 w-4" aria-hidden />
                          )
                        ) : null}
                        <span>
                          {evo > 0 ? "+" : ""}
                          {evo.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}% vs mois
                          précédent
                        </span>
                      </div>
                    </div>
                    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                      {absenceDonutData.length > 0 ? (
                        <div
                          className="h-[220px] w-full min-w-0"
                          aria-label="Répartition des jours d'absence"
                        >
                          <ResponsiveContainer width="100%" height={220}>
                            <PieChart>
                              <Pie
                                data={absenceDonutData}
                                dataKey="value"
                                nameKey="name"
                                cx="50%"
                                cy="50%"
                                innerRadius={50}
                                outerRadius={78}
                                paddingAngle={2}
                              >
                                {absenceDonutData.map((entry) => (
                                  <Cell key={entry.name} fill={entry.fill} />
                                ))}
                              </Pie>
                              <RechartsTooltip
                                formatter={(v: number) => [`${v} jours`, ""]}
                              />
                              <Legend wrapperStyle={{ fontSize: 11 }} />
                            </PieChart>
                          </ResponsiveContainer>
                        </div>
                      ) : (
                        <EmptyChartState
                          icon={Calendar}
                          title="Aucune absence sur la période"
                          description="Les absences validées des 30 derniers jours apparaîtront ici."
                        />
                      )}
                      <div className="flex flex-col justify-center gap-2 rounded-lg border bg-muted/20 p-4 text-sm">
                        <div className="flex justify-between gap-2">
                          <span>Maladie</span>
                          <span className="tabular-nums font-medium">
                            {data.absenteisme.taux_maladie.toFixed(1)}% —{" "}
                            {data.absenteisme.jours_perdus_maladie} j.
                          </span>
                        </div>
                        <div className="flex justify-between gap-2">
                          <span>Accident du travail</span>
                          <span className="tabular-nums font-medium">
                            {data.absenteisme.taux_at.toFixed(1)}% —{" "}
                            {data.absenteisme.jours_perdus_at} j.
                          </span>
                        </div>
                        <div className="flex justify-between gap-2">
                          <span>Autres absences</span>
                          <span className="tabular-nums font-medium">
                            {data.absenteisme.taux_autres.toFixed(1)}% —{" "}
                            {data.absenteisme.jours_perdus_autres} j.
                          </span>
                        </div>
                        <div className="border-t pt-2 flex justify-between gap-2 font-semibold">
                          <span>Total jours perdus</span>
                          <span className="tabular-nums">
                            {data.absenteisme.jours_perdus_total}
                          </span>
                        </div>
                      </div>
                    </div>
                  </>
                ) : null}
              </CardContent>
            </Card>
          </section>

          {/* Section 4 — Paie */}
          <section aria-labelledby="section-paie" className="mt-6">
            <SectionHeading
              title="Masse salariale"
              subtitle={
                data
                  ? `Total brut mensuel de base : ${eur.format(data.masse_salariale_brute_totale)}`
                  : "Répartition par service"
              }
            />
            <Card>
              <CardHeader className="p-4 pb-0">
                <CardTitle className="text-base">Masse salariale par service</CardTitle>
                <CardDescription>Somme des salaires de base (brut mensuel)</CardDescription>
              </CardHeader>
              <CardContent className="p-4 pt-2">
                {data && masseChartData.length > 0 ? (
                  <div
                    className="h-[280px] w-full min-w-0"
                    aria-label="Masse salariale par service"
                  >
                    <ResponsiveContainer width="100%" height={280}>
                      <BarChart
                        data={masseChartData}
                        margin={{ bottom: 56, left: 4, right: 8, top: 4 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                        <XAxis
                          dataKey="service"
                          angle={-35}
                          textAnchor="end"
                          height={64}
                          interval={0}
                          tick={{ fontSize: 9 }}
                        />
                        <YAxis
                          width={48}
                          tick={{ fontSize: 9 }}
                          tickFormatter={(v) =>
                            Number(v).toLocaleString("fr-FR", { maximumFractionDigits: 0 })
                          }
                        />
                        <RechartsTooltip
                          formatter={(v: number) => [eur.format(v), "Masse brute"]}
                        />
                        <Bar
                          dataKey="masse"
                          fill="hsl(var(--primary))"
                          name="Masse"
                          radius={[4, 4, 0, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <EmptyChartState
                    icon={BarChart3}
                    title="Masse salariale indisponible"
                    description="Renseignez les salaires de base et les services sur les fiches salariés."
                  />
                )}
              </CardContent>
            </Card>
          </section>

          {/* Section 5 — Anomalies paie */}
          <section id="anomalies-paie" aria-labelledby="section-anomalies" className="mt-6">
            <SectionHeading
              title="Anomalies de paie"
              subtitle={`Contrôles automatiques — ${periodLabel}`}
              right={
                anomaliesFetching && !anomaliesLoading ? (
                  <RefreshCw
                    className="text-muted-foreground h-4 w-4 animate-spin"
                    aria-label="Mise à jour des anomalies"
                  />
                ) : null
              }
            />
            {anomaliesPeriodHint ? (
              <p className="text-muted-foreground -mt-2 mb-2 text-xs">{anomaliesPeriodHint}</p>
            ) : null}
            <Card
              className={
                anomaliesFetching && anomaliesData
                  ? "opacity-80 transition-opacity duration-150"
                  : undefined
              }
            >
              <CardContent className="space-y-3 p-4">
                {anomaliesError ? (
                  <Alert variant="destructive">
                    <AlertTitle>Anomalies</AlertTitle>
                    <AlertDescription>
                      {anomaliesError instanceof Error
                        ? anomaliesError.message
                        : "Erreur de chargement."}
                    </AlertDescription>
                  </Alert>
                ) : null}
                {anomaliesLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : anomaliesData ? (
                  <>
                    <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
                      <Card>
                        <CardContent className="p-3">
                          <p className="text-2xl font-bold tabular-nums">
                            {anomaliesData.total_bulletins}
                          </p>
                          <p className="text-muted-foreground text-xs">Bulletins analysés</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3">
                          <p className="text-2xl font-bold tabular-nums">
                            {anomaliesData.bulletins_avec_anomalies}
                          </p>
                          <p className="text-muted-foreground text-xs">Avec anomalies</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3">
                          <p className="text-2xl font-bold tabular-nums text-red-600">
                            {anomaliesSummary.bloquants}
                          </p>
                          <p className="text-muted-foreground text-xs">Bloquants</p>
                        </CardContent>
                      </Card>
                      <Card>
                        <CardContent className="p-3">
                          <p className="text-2xl font-bold tabular-nums text-amber-600">
                            {anomaliesSummary.avertissements}
                          </p>
                          <p className="text-muted-foreground text-xs">Avertissements</p>
                        </CardContent>
                      </Card>
                    </div>
                    {anomaliesData.anomalies.length === 0 ? (
                      <p className="text-muted-foreground py-4 text-center text-sm">
                        Aucune anomalie détectée pour {periodLabel}.
                      </p>
                    ) : (
                      <div className="w-full overflow-x-auto rounded-md border">
                        <Table className="text-sm [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2">
                          <TableHeader>
                            <TableRow>
                              <TableHead>Salarié</TableHead>
                              <TableHead>Type</TableHead>
                              <TableHead>Sévérité</TableHead>
                              <TableHead>Détail</TableHead>
                              <TableHead className="text-right">Action</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {anomaliesData.anomalies.map((row, idx) => (
                              <TableRow key={`${row.payslip_id}-${row.type}-${idx}`}>
                                <TableCell className="max-w-[10rem] truncate font-medium">
                                  {row.employee_name}
                                </TableCell>
                                <TableCell className="max-w-[6rem] truncate text-muted-foreground text-xs">
                                  {row.type}
                                </TableCell>
                                <TableCell>
                                  <Badge
                                    variant="secondary"
                                    className={
                                      row.severite === "bloquant"
                                        ? "bg-red-600 text-white hover:bg-red-600"
                                        : "bg-amber-600 text-white hover:bg-amber-600"
                                    }
                                  >
                                    {row.severite === "bloquant"
                                      ? "Bloquant"
                                      : "Avertissement"}
                                  </Badge>
                                </TableCell>
                                <TableCell className="max-w-[220px] text-xs">
                                  <span className="line-clamp-2" title={row.message}>
                                    {row.message}
                                  </span>
                                  {row.valeur_detectee ? (
                                    <span className="text-muted-foreground block truncate">
                                      {row.valeur_detectee}
                                    </span>
                                  ) : null}
                                </TableCell>
                                <TableCell className="text-right">
                                  <Button variant="ghost" size="sm" className="h-8" asChild>
                                    <Link
                                      to={`/payslips/${row.payslip_id}/edit`}
                                      title="Ouvrir le bulletin"
                                    >
                                      <ExternalLink className="mr-1 h-3.5 w-3.5" />
                                      Bulletin
                                    </Link>
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                  </>
                ) : null}
              </CardContent>
            </Card>
          </section>

          {/* Section 6 — Journal d'activité */}
          <section aria-labelledby="section-audit" className="mt-6">
            <Collapsible open={auditOpen} onOpenChange={setAuditOpen}>
              <Card>
                <CollapsibleTrigger asChild>
                  <button
                    type="button"
                    className="flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-muted/40 transition-colors rounded-t-lg"
                    aria-expanded={auditOpen}
                  >
                    <div>
                      <h2
                        id="section-audit"
                        className="text-lg font-semibold leading-tight tracking-tight"
                      >
                        Journal d&apos;activité et conformité
                      </h2>
                      <p className="text-muted-foreground text-sm">
                        Traçabilité des actions sensibles (RGPD, audits internes)
                      </p>
                    </div>
                    <ChevronDown
                      className={`text-muted-foreground h-5 w-5 shrink-0 transition-transform ${auditOpen ? "rotate-180" : ""}`}
                      aria-hidden
                    />
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent>
                  <CardContent className="space-y-3 border-t p-4 pt-3">
                    <div className="flex flex-wrap items-end gap-3">
                      <div className="min-w-[140px] flex-1 space-y-1">
                        <Label className="text-xs">Type de ressource</Label>
                        <Select
                          value={auditResourceType || "__all__"}
                          onValueChange={(v) =>
                            setAuditResourceType(v === "__all__" ? "" : v)
                          }
                        >
                          <SelectTrigger className="h-9 w-full">
                            <SelectValue placeholder="Tous" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__all__">Tous</SelectItem>
                            <SelectItem value="employee">Salarié</SelectItem>
                            <SelectItem value="payslip">Bulletin de paie</SelectItem>
                            <SelectItem value="absence_request">Absence</SelectItem>
                            <SelectItem value="candidate">Candidat</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="min-w-[120px] flex-1 space-y-1">
                        <Label htmlFor="audit-since" className="text-xs">
                          Depuis
                        </Label>
                        <Input
                          id="audit-since"
                          type="date"
                          value={auditSince}
                          onChange={(e) => setAuditSince(e.target.value)}
                          className="h-9 w-full min-w-0"
                        />
                      </div>
                      <div className="min-w-[120px] flex-1 space-y-1">
                        <Label htmlFor="audit-until" className="text-xs">
                          Jusqu&apos;au
                        </Label>
                        <Input
                          id="audit-until"
                          type="date"
                          value={auditUntil}
                          onChange={(e) => setAuditUntil(e.target.value)}
                          className="h-9 w-full min-w-0"
                        />
                      </div>
                      <Button
                        type="button"
                        variant="secondary"
                        size="sm"
                        className="shrink-0"
                        disabled={auditFetching}
                        onClick={() => void refetchAudit()}
                      >
                        Filtrer
                      </Button>
                    </div>
                    {auditError ? (
                      <Alert variant="destructive">
                        <AlertTitle>Journal</AlertTitle>
                        <AlertDescription>
                          {auditError instanceof Error
                            ? auditError.message
                            : "Erreur de chargement."}
                        </AlertDescription>
                      </Alert>
                    ) : null}
                    {auditLoading && !auditData ? (
                      <Skeleton className="h-32 w-full" />
                    ) : (
                      <div className="w-full overflow-x-auto rounded-md border">
                        <Table className="text-sm [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2">
                          <TableHeader>
                            <TableRow>
                              <TableHead>Date</TableHead>
                              <TableHead>Utilisateur</TableHead>
                              <TableHead>Action</TableHead>
                              <TableHead>Ressource</TableHead>
                              <TableHead>Détails</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {(auditData ?? []).length === 0 ? (
                              <TableRow>
                                <TableCell
                                  colSpan={5}
                                  className="text-muted-foreground px-3 py-6 text-center text-sm"
                                >
                                  Aucune entrée pour ces filtres.
                                </TableCell>
                              </TableRow>
                            ) : (
                              (auditData ?? []).map((row: AuditLogEntry) => (
                                <TableRow key={row.id}>
                                  <TableCell className="whitespace-nowrap text-xs">
                                    {new Date(row.created_at).toLocaleString("fr-FR")}
                                  </TableCell>
                                  <TableCell className="max-w-[8rem] truncate text-xs">
                                    {row.user_email || row.user_id || "—"}
                                  </TableCell>
                                  <TableCell className="text-xs">
                                    {ACTIONS_LABELS[row.action] || row.action}
                                  </TableCell>
                                  <TableCell className="max-w-[7rem] truncate text-xs">
                                    {row.resource_type}
                                    {row.resource_id ? ` / ${row.resource_id.slice(0, 8)}…` : ""}
                                  </TableCell>
                                  <TableCell className="max-w-[180px] truncate text-xs text-muted-foreground">
                                    {row.details ? JSON.stringify(row.details) : "—"}
                                  </TableCell>
                                </TableRow>
                              ))
                            )}
                          </TableBody>
                        </Table>
                      </div>
                    )}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      disabled={
                        auditFetching || !auditData || auditData.length < auditLimit
                      }
                      onClick={() => setAuditLimit((l) => l + 50)}
                    >
                      Charger plus
                    </Button>
                  </CardContent>
                </CollapsibleContent>
              </Card>
            </Collapsible>
          </section>
        </>
      )}
    </div>
  );
}
