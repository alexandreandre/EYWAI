import { RhPageHeader } from '@/components/layout';
import { useCallback, useMemo, useState } from "react";
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
  Download,
  Handshake,
  MessageSquare,
  RefreshCw,
  Stethoscope,
  TrendingUp,
} from "lucide-react";

import { getAnalyticsGestion } from "@/api/analyticsGestion";
import { useCompany } from "@/contexts/CompanyContext";
import { AnalyticsPeriodControls } from "@/components/analytics/AnalyticsPeriodControls";
import { EmptyChartState } from "@/components/analytics/EmptyChartState";
import { KpiCard } from "@/components/analytics/KpiCard";
import { SectionHeading } from "@/components/analytics/SectionHeading";
import { SectionSkeleton } from "@/components/analytics/SectionSkeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { CHART_CONTRACT_COLORS } from "@/lib/analyticsChartColors";
import {
  buildPeriodBounds,
  defaultPeriodSelection,
  MONTH_NAMES_FR,
  type PeriodSelection,
} from "@/lib/analyticsPeriod";
import { exportAnalyticsGestionXlsx } from "@/lib/exportAnalyticsGestionXlsx";

const STATUS_LABELS: Record<string, string> = {
  planifie: "Planifié",
  en_attente_acceptation: "En attente acceptation",
  accepte: "Accepté",
  refuse: "Refusé",
  realise: "Réalisé",
  cloture: "Clôturé",
};

const eur = new Intl.NumberFormat("fr-FR", {
  style: "currency",
  currency: "EUR",
  maximumFractionDigits: 0,
});

function budgetAlertBadge(level: string): { label: string; className: string } | null {
  if (level === "critical") {
    return { label: "Critique", className: "bg-red-600 hover:bg-red-600" };
  }
  if (level === "warning") {
    return { label: "Attention", className: "bg-amber-600 hover:bg-amber-600" };
  }
  return null;
}

export default function AnalyticsGestion(): JSX.Element {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? null;

  const [periodSelection, setPeriodSelection] = useState<PeriodSelection>(() =>
    defaultPeriodSelection(),
  );
  const periodBounds = useMemo(
    () => buildPeriodBounds(periodSelection),
    [periodSelection],
  );

  const { data, isLoading, isFetching, error, refetch } = useQuery({
    queryKey: [
      "analytics-gestion",
      companyId,
      periodBounds.start,
      periodBounds.end,
    ],
    queryFn: () =>
      getAnalyticsGestion(companyId, {
        period_start: periodBounds.start,
        period_end: periodBounds.end,
      }),
    enabled: Boolean(companyId),
    placeholderData: (previous) => previous,
  });

  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  const entretiensChartData = useMemo(() => {
    if (!data?.entretiens.by_status) return [];
    return Object.entries(data.entretiens.by_status)
      .filter(([, count]) => count > 0)
      .map(([status, count]) => ({
        name: STATUS_LABELS[status] ?? status,
        value: count,
      }));
  }, [data]);

  const promotionsChartData = useMemo(() => {
    if (!data?.carriere.promotions_by_month) return [];
    return Object.entries(data.carriere.promotions_by_month)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([month, count]) => ({
        month: month.slice(5),
        count,
      }));
  }, [data]);

  const conformiteRisk =
    (data?.conformite.certifications_expired ?? 0) +
    (data?.conformite.legal_obligations_overdue ?? 0);

  const cseAlerts =
    (data?.cse.mandate_alerts_count ?? 0) + (data?.cse.election_critical_count ?? 0);

  if (!companyId) {
    return (
      <div className="container max-w-6xl">
        <Alert>
          <AlertTitle>Entreprise requise</AlertTitle>
          <AlertDescription>
            Sélectionnez une entreprise pour afficher Analytics Gestion.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const showInitialSkeleton = isLoading && !data;
  const budgetB = data ? budgetAlertBadge(data.formation.budget_alert_level) : null;

  return (
    <div className="container max-w-7xl space-y-6">
      <header className="space-y-4">
        <RhPageHeader
          title="Analytics Gestion"
          description={`Pilotage RH — entretiens, formation, calendriers, médical, carrière et CSE — ${activeCompany?.company_name ?? '—'}`}
          actions={
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
                  className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`}
                />
                Actualiser
              </Button>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="h-9"
                disabled={!data}
                onClick={() => {
                  void exportAnalyticsGestionXlsx(
                    activeCompany?.company_name ?? 'entreprise',
                    periodBounds.label,
                    periodBounds.exportKey,
                    data,
                  );
                }}
              >
                <Download className="mr-2 h-4 w-4" />
                Exporter Excel
              </Button>
            </div>
          }
        />

        <AnalyticsPeriodControls
          value={periodSelection}
          onChange={setPeriodSelection}
          periodLabel={periodBounds.label}
          hint="Budget formation, objectifs et promotions : année de la période. Médical, CSE et calendriers : état au jour le plus récent."
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

      {showInitialSkeleton ? (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full rounded-lg" />
          ))}
        </div>
      ) : data ? (
        <div
          className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6"
          aria-label="Indicateurs clés gestion"
        >
          <KpiCard
            label="Entretiens à traiter"
            value={data.entretiens.actionable_count}
            hint={
              data.entretiens.overdue_count > 0
                ? `${data.entretiens.overdue_count} en retard`
                : `${data.entretiens.upcoming_14d_count} sous 14 j`
            }
            href="/annual-reviews"
          />
          <KpiCard
            label="Conformité"
            value={conformiteRisk}
            hint="Habilitations expirées + obligations légales en retard"
            href="/formation#conformite"
          />
          <KpiCard
            label="Médical"
            value={data.medical.overdue_count + data.medical.due_within_30_count}
            hint={`${data.medical.overdue_count} retard · ${data.medical.due_within_30_count} sous 30 j`}
            href="/medical-follow-up"
          />
          <KpiCard
            label="Calendriers"
            value={data.calendriers.a_saisir + data.calendriers.avec_ecart}
            hint={`${data.calendriers.a_saisir} à saisir · ${data.calendriers.avec_ecart} écarts`}
            href="/schedules"
          />
          <KpiCard
            label="Budget formation"
            value={
              data.formation.budget_envelope > 0
                ? `${data.formation.budget_consumption_pct.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} %`
                : "—"
            }
            badge={
              budgetB ? (
                <Badge className={budgetB.className} variant="default">
                  {budgetB.label}
                </Badge>
              ) : null
            }
            hint={
              data.formation.budget_envelope > 0
                ? `${eur.format(data.formation.budget_consumed)} / ${eur.format(data.formation.budget_envelope)}`
                : "Budget non défini"
            }
            href="/formation#formations"
          />
          <KpiCard
            label="Alertes CSE"
            value={cseAlerts}
            hint={`${data.cse.mandate_alerts_count} mandats · ${data.cse.election_critical_count} élections critiques`}
            href="/cse"
          />
        </div>
      ) : null}

      {showInitialSkeleton ? (
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <SectionSkeleton />
            <SectionSkeleton />
          </div>
          <SectionSkeleton />
          <SectionSkeleton />
        </div>
      ) : data ? (
        <>
          <section aria-labelledby="section-entretiens">
            <SectionHeading
              title="Entretiens & performance"
              subtitle={`Année ${data.period.year} — taux de clôture ${data.entretiens.closure_rate_pct.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`}
            />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Répartition par statut</CardTitle>
                  <CardDescription>Entretiens de l&apos;année sélectionnée</CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  {entretiensChartData.length > 0 ? (
                    <div className="h-[240px] w-full min-w-0" aria-label="Statuts entretiens">
                      <ResponsiveContainer width="100%" height={240}>
                        <PieChart>
                          <Pie
                            data={entretiensChartData}
                            dataKey="value"
                            nameKey="name"
                            cx="50%"
                            cy="50%"
                            innerRadius={52}
                            outerRadius={80}
                            paddingAngle={2}
                          >
                            {entretiensChartData.map((_, i) => (
                              <Cell
                                key={entretiensChartData[i].name}
                                fill={
                                  CHART_CONTRACT_COLORS[i % CHART_CONTRACT_COLORS.length]
                                }
                              />
                            ))}
                          </Pie>
                          <RechartsTooltip />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartState
                      icon={MessageSquare}
                      title="Aucun entretien"
                      description="Créez les entretiens annuels pour l'année sélectionnée."
                    />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Objectifs & échéances</CardTitle>
                  <CardDescription>Actions prioritaires entretiens</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 p-4 pt-2">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div className="rounded-lg border bg-muted/20 p-3">
                      <p className="text-muted-foreground text-xs">À traiter</p>
                      <p className="text-2xl font-bold tabular-nums">
                        {data.entretiens.actionable_count}
                      </p>
                    </div>
                    <div className="rounded-lg border bg-muted/20 p-3">
                      <p className="text-muted-foreground text-xs">En retard</p>
                      <p className="text-2xl font-bold tabular-nums text-red-600">
                        {data.entretiens.overdue_count}
                      </p>
                    </div>
                    <div className="rounded-lg border bg-muted/20 p-3">
                      <p className="text-muted-foreground text-xs">Sous 14 jours</p>
                      <p className="text-2xl font-bold tabular-nums">
                        {data.entretiens.upcoming_14d_count}
                      </p>
                    </div>
                    <div className="rounded-lg border bg-muted/20 p-3">
                      <p className="text-muted-foreground text-xs">Taux objectifs</p>
                      <p className="text-2xl font-bold tabular-nums">
                        {data.objectives.achievement_rate_pct != null
                          ? `${data.objectives.achievement_rate_pct.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %`
                          : "—"}
                      </p>
                    </div>
                  </div>
                  {data.entretiens.overdue_count > 0 ? (
                    <Alert variant="destructive">
                      <AlertTriangle className="h-4 w-4" />
                      <AlertTitle>Entretiens en retard</AlertTitle>
                      <AlertDescription>
                        {data.entretiens.overdue_count} entretien
                        {data.entretiens.overdue_count > 1 ? "s" : ""} ont dépassé la date
                        prévue.
                      </AlertDescription>
                    </Alert>
                  ) : null}
                </CardContent>
              </Card>
            </div>
          </section>

          <section aria-labelledby="section-formation" className="mt-6">
            <SectionHeading
              title="Formation & conformité"
              subtitle={`Budget ${data.period.year} et habilitations`}
            />
            <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <Card>
                <CardContent className="space-y-2 p-4">
                  <p className="text-muted-foreground text-xs font-medium uppercase">
                    Budget consommé
                  </p>
                  <p className="text-3xl font-bold tabular-nums">
                    {data.formation.budget_envelope > 0
                      ? `${data.formation.budget_consumption_pct.toLocaleString("fr-FR", { maximumFractionDigits: 0 })} %`
                      : "—"}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    {data.formation.budget_envelope > 0
                      ? `${eur.format(data.formation.budget_consumed)} sur ${eur.format(data.formation.budget_envelope)}`
                      : "Définir le budget dans Formation"}
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="space-y-2 p-4">
                  <p className="text-muted-foreground text-xs font-medium uppercase">
                    Habilitations
                  </p>
                  <p className="text-3xl font-bold tabular-nums text-red-600">
                    {data.conformite.certifications_expired}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    expirées · {data.conformite.certifications_expiring} expire bientôt
                  </p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="space-y-2 p-4">
                  <p className="text-muted-foreground text-xs font-medium uppercase">
                    Obligations légales
                  </p>
                  <p className="text-3xl font-bold tabular-nums text-amber-600">
                    {data.conformite.legal_obligations_overdue}
                  </p>
                  <p className="text-muted-foreground text-xs">
                    en retard · {data.conformite.legal_obligations_due_soon} à échéance
                  </p>
                </CardContent>
              </Card>
            </div>
            {data.formation.evaluations_count > 0 ? (
              <p className="text-muted-foreground mt-2 text-xs">
                Satisfaction formations : note moyenne{" "}
                {data.formation.evaluations_average?.toLocaleString("fr-FR", {
                  maximumFractionDigits: 1,
                }) ?? "—"}{" "}
                / 5 ({data.formation.evaluations_count} formation
                {data.formation.evaluations_count > 1 ? "s" : ""} évaluée
                {data.formation.evaluations_count > 1 ? "s" : ""})
              </p>
            ) : null}
          </section>

          <section aria-labelledby="section-calendriers" className="mt-6">
            <SectionHeading
              title="Calendriers & suivi médical"
              subtitle={`Calendriers paie — ${MONTH_NAMES_FR[data.period.calendar_month - 1] ?? ""} ${data.period.calendar_year}`}
            />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Calendriers paie</CardTitle>
                  <CardDescription>
                    {data.calendriers.saisis} / {data.calendriers.total} salariés saisis
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 p-4 pt-2">
                  <div>
                    <div className="mb-1 flex justify-between text-xs">
                      <span className="text-muted-foreground">Progression</span>
                      <span className="font-medium tabular-nums">
                        {data.calendriers.progress_percent} %
                      </span>
                    </div>
                    <Progress value={data.calendriers.progress_percent} className="h-2" />
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="flex justify-between rounded-lg border p-2">
                      <span>À saisir</span>
                      <span className="font-semibold tabular-nums text-amber-600">
                        {data.calendriers.a_saisir}
                      </span>
                    </div>
                    <div className="flex justify-between rounded-lg border p-2">
                      <span>Avec écart</span>
                      <span className="font-semibold tabular-nums text-red-600">
                        {data.calendriers.avec_ecart}
                      </span>
                    </div>
                    <div className="flex justify-between rounded-lg border p-2">
                      <span>Conflits absences</span>
                      <span className="font-semibold tabular-nums">
                        {data.calendriers.conflits_absences}
                      </span>
                    </div>
                    <div className="flex justify-between rounded-lg border p-2">
                      <span>Saisis</span>
                      <span className="font-semibold tabular-nums text-emerald-600">
                        {data.calendriers.saisis}
                      </span>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Suivi médical</CardTitle>
                  <CardDescription>
                    Taux de conformité {data.medical.compliance_rate_pct.toLocaleString("fr-FR", { maximumFractionDigits: 1 })} %
                  </CardDescription>
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  <div className="mb-3 grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded-lg border bg-muted/20 p-2">
                      <span className="text-muted-foreground text-xs">En retard</span>
                      <p className="text-xl font-bold tabular-nums text-red-600">
                        {data.medical.overdue_count}
                      </p>
                    </div>
                    <div className="rounded-lg border bg-muted/20 p-2">
                      <span className="text-muted-foreground text-xs">Échéance 30 j</span>
                      <p className="text-xl font-bold tabular-nums">
                        {data.medical.due_within_30_count}
                      </p>
                    </div>
                  </div>
                  {data.medical.employees_overdue_top.length > 0 ? (
                    <div className="overflow-x-auto rounded-md border">
                      <Table className="text-sm [&_td]:px-3 [&_td]:py-2 [&_th]:px-3 [&_th]:py-2">
                        <TableHeader>
                          <TableRow>
                            <TableHead>Salarié</TableHead>
                            <TableHead className="text-right">Retards</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {data.medical.employees_overdue_top.map((row) => (
                            <TableRow key={row.employee_id}>
                              <TableCell className="max-w-[12rem] truncate font-medium">
                                {row.employee_name}
                              </TableCell>
                              <TableCell className="text-right tabular-nums">
                                {row.obligations_overdue}
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>
                  ) : (
                    <EmptyChartState
                      icon={Stethoscope}
                      title="Aucun retard médical"
                      description="Les obligations de visite sont à jour."
                      heightClass="h-[160px]"
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          </section>

          <section aria-labelledby="section-carriere" className="mt-6">
            <SectionHeading
              title="Carrière & CSE"
              subtitle={`Promotions ${data.period.year} et dialogue social`}
            />
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">Carrière</CardTitle>
                  <CardDescription>
                    {data.carriere.total_promotions} promotions · taux d&apos;approbation{" "}
                    {data.carriere.approval_rate_pct.toLocaleString("fr-FR", {
                      maximumFractionDigits: 0,
                    })}
                    %
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-4 pt-2">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded-lg border p-2">
                      <span className="text-muted-foreground text-xs">Brouillons</span>
                      <p className="font-semibold tabular-nums">
                        {data.carriere.promotions_draft_count}
                      </p>
                    </div>
                    <div className="rounded-lg border p-2">
                      <span className="text-muted-foreground text-xs">Avenants à signer</span>
                      <p className="font-semibold tabular-nums">
                        {data.carriere.avenants_pending_signature}
                      </p>
                    </div>
                  </div>
                  {promotionsChartData.length > 0 ? (
                    <div className="h-[200px] w-full min-w-0" aria-label="Promotions par mois">
                      <ResponsiveContainer width="100%" height={200}>
                        <BarChart data={promotionsChartData} margin={{ bottom: 8, left: 4, right: 8 }}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis dataKey="month" tick={{ fontSize: 10 }} />
                          <YAxis allowDecimals={false} width={28} tick={{ fontSize: 10 }} />
                          <RechartsTooltip />
                          <Bar
                            dataKey="count"
                            fill="hsl(var(--primary))"
                            radius={[4, 4, 0, 0]}
                            name="Promotions"
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <EmptyChartState
                      icon={TrendingUp}
                      title="Aucune promotion"
                      description="Les promotions de l'année apparaîtront ici."
                      heightClass="h-[160px]"
                    />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="p-4 pb-0">
                  <CardTitle className="text-base">CSE & dialogue social</CardTitle>
                  <CardDescription>Mandats, élections et délégation</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 p-4 pt-2">
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <div className="rounded-lg border p-2">
                      <span className="text-muted-foreground text-xs">Mandats à surveiller</span>
                      <p className="font-semibold tabular-nums">
                        {data.cse.mandate_alerts_count}
                      </p>
                    </div>
                    <div className="rounded-lg border p-2">
                      <span className="text-muted-foreground text-xs">Alertes électorales</span>
                      <p className="font-semibold tabular-nums">
                        {data.cse.election_alerts_count}
                      </p>
                    </div>
                    <div className="rounded-lg border p-2 col-span-2">
                      <span className="text-muted-foreground text-xs">
                        Heures délégation (mois courant)
                      </span>
                      <p className="font-semibold tabular-nums">
                        {data.cse.delegation_consumed_hours.toLocaleString("fr-FR", {
                          maximumFractionDigits: 1,
                        })}{" "}
                        h /{" "}
                        {data.cse.delegation_quota_hours.toLocaleString("fr-FR", {
                          maximumFractionDigits: 1,
                        })}{" "}
                        h
                        {data.cse.delegation_over_quota_count > 0
                          ? ` · ${data.cse.delegation_over_quota_count} dépassement(s)`
                          : ""}
                      </p>
                    </div>
                  </div>
                  {data.cse.upcoming_meetings.length > 0 ? (
                    <ul className="space-y-2 text-sm">
                      {data.cse.upcoming_meetings.map((m) => (
                        <li
                          key={m.id}
                          className="flex items-center justify-between gap-2 rounded-lg border px-3 py-2"
                        >
                          <span className="min-w-0 truncate font-medium">{m.title}</span>
                          <span className="text-muted-foreground shrink-0 text-xs tabular-nums">
                            {new Date(m.meeting_date).toLocaleDateString("fr-FR")}
                          </span>
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <EmptyChartState
                      icon={Handshake}
                      title="Aucune réunion à venir"
                      description="Planifiez les prochaines réunions CSE."
                      heightClass="h-[120px]"
                    />
                  )}
                </CardContent>
              </Card>
            </div>
          </section>
        </>
      ) : null}
    </div>
  );
}
