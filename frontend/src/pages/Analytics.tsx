import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  ResponsiveContainer,
  Tooltip as RechartsTooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ArrowDownRight, ArrowUpRight, RefreshCw } from "lucide-react";

import {
  ACTIONS_LABELS,
  createWebhook,
  deleteWebhook,
  getAnalyticsAvances,
  getAnomaliesPayslips,
  getAuditLogs,
  getWebhookLogs,
  getWebhooks,
  testWebhook,
  updateWebhook,
  WEBHOOK_EVENTS,
  type AnalyticsAvances,
  type AuditLogEntry,
  type WebhookConfig,
  type WebhookLog,
} from "@/api/analytics";
import { getApiBaseUrl } from "@/api/apiClient";
import { useAuth } from "@/contexts/AuthContext";
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/hooks/use-toast";

const CHART_PYRAMID_COLORS = [
  "hsl(var(--primary))",
  "hsl(var(--primary) / 0.88)",
  "hsl(var(--primary) / 0.76)",
  "hsl(var(--primary) / 0.64)",
  "hsl(var(--primary) / 0.52)",
  "hsl(var(--primary) / 0.4)",
];

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
          <p className="text-muted-foreground line-clamp-1 text-sm">{subtitle}</p>
        ) : null}
      </div>
      {right ? <div className="shrink-0">{right}</div> : null}
    </div>
  );
}

function payrollPeriodFromYm(y: number, m: number): string {
  return `${y}-${String(m).padStart(2, "0")}`;
}

export default function Analytics(): JSX.Element {
  const { activeCompany } = useCompany();
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const companyId = activeCompany?.company_id ?? null;

  const canManageWebhooks = useMemo(() => {
    if (user?.is_super_admin) return true;
    const cr = activeCompany?.role ?? user?.role;
    return cr === "rh" || cr === "admin" || cr === "collaborateur_rh";
  }, [activeCompany?.role, user?.is_super_admin, user?.role]);

  /** OpenAPI FastAPI : même origine que axios (VITE_API_URL), pas le host Vite. */
  const openapiDocsUrl = useMemo(() => {
    let base = getApiBaseUrl().trim().replace(/\/+$/, "");
    if (!base) base = "http://localhost:8000";
    return `${base}/docs`;
  }, []);

  const now = useMemo(() => new Date(), []);
  const [payrollYm, setPayrollYm] = useState(() =>
    payrollPeriodFromYm(now.getFullYear(), now.getMonth() + 1),
  );
  const payrollYear = useMemo(() => parseInt(payrollYm.slice(0, 4), 10), [payrollYm]);
  const payrollMonth = useMemo(() => parseInt(payrollYm.slice(5, 7), 10), [payrollYm]);

  const [auditResourceType, setAuditResourceType] = useState<string>("");
  const [auditSince, setAuditSince] = useState("");
  const [auditUntil, setAuditUntil] = useState("");
  const [auditLimit, setAuditLimit] = useState(50);

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
    error: anomaliesError,
    refetch: refetchAnomalies,
  } = useQuery({
    queryKey: ["payslips-anomalies", companyId, payrollYear, payrollMonth],
    queryFn: () => getAnomaliesPayslips(companyId, payrollYear, payrollMonth),
    enabled: Boolean(companyId),
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
    enabled: Boolean(companyId),
  });

  const [whCreateOpen, setWhCreateOpen] = useState(false);
  const [whName, setWhName] = useState("");
  const [whUrl, setWhUrl] = useState("");
  const [whSecret, setWhSecret] = useState("");
  const [whEventsPick, setWhEventsPick] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(WEBHOOK_EVENTS.map((e) => [e, false])),
  );
  const [logsWhId, setLogsWhId] = useState<string | null>(null);

  const {
    data: webhooksData,
    isLoading: whLoading,
  } = useQuery({
    queryKey: ["webhooks", companyId],
    queryFn: () => getWebhooks(companyId),
    enabled: Boolean(companyId) && canManageWebhooks,
  });

  const { data: whLogsData, isFetching: whLogsFetching } = useQuery({
    queryKey: ["webhook-logs", companyId, logsWhId],
    queryFn: () => getWebhookLogs(logsWhId!, companyId),
    enabled: Boolean(companyId && logsWhId && canManageWebhooks),
  });

  const createWhMutation = useMutation({
    mutationFn: () => {
      const events = WEBHOOK_EVENTS.filter((e) => whEventsPick[e]);
      return createWebhook(companyId, {
        name: whName.trim(),
        url: whUrl.trim(),
        secret: whSecret.trim() || undefined,
        events,
      });
    },
    onSuccess: () => {
      toast({ title: "Webhook créé" });
      setWhCreateOpen(false);
      setWhName("");
      setWhUrl("");
      setWhSecret("");
      setWhEventsPick(Object.fromEntries(WEBHOOK_EVENTS.map((e) => [e, false])));
      void queryClient.invalidateQueries({ queryKey: ["webhooks", companyId] });
    },
    onError: (e: Error) => {
      toast({
        title: "Erreur",
        description: e.message,
        variant: "destructive",
      });
    },
  });

  const deleteWhMutation = useMutation({
    mutationFn: (id: string) => deleteWebhook(id, companyId),
    onSuccess: () => {
      toast({ title: "Webhook supprimé" });
      void queryClient.invalidateQueries({ queryKey: ["webhooks", companyId] });
    },
    onError: (e: Error) => {
      toast({
        title: "Erreur",
        description: e.message,
        variant: "destructive",
      });
    },
  });

  const testWhMutation = useMutation({
    mutationFn: (id: string) => testWebhook(id, companyId),
    onSuccess: (r) => {
      toast({
        title: r.success ? "Test réussi" : "Test terminé",
        description: `HTTP ${r.status_code}`,
        ...(r.success ? {} : { variant: "destructive" as const }),
      });
    },
    onError: (e: Error) => {
      toast({
        title: "Erreur test",
        description: e.message,
        variant: "destructive",
      });
    },
  });

  const toggleWhMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateWebhook(id, companyId, { is_active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["webhooks", companyId] });
    },
    onError: (e: Error) => {
      toast({
        title: "Erreur",
        description: e.message,
        variant: "destructive",
      });
    },
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

  const absStack = useMemo(() => {
    if (!data) return { mal: 0, at: 0, aut: 0 };
    const t = data.absenteisme.jours_perdus_total;
    if (t <= 0) return { mal: 0, at: 0, aut: 0 };
    const m = data.absenteisme.jours_perdus_maladie;
    const a = data.absenteisme.jours_perdus_at;
    const o = data.absenteisme.jours_perdus_autres;
    return {
      mal: (100 * m) / t,
      at: (100 * a) / t,
      aut: (100 * o) / t,
    };
  }, [data]);

  if (!companyId) {
    return (
      <div className="container max-w-6xl py-8">
        <Alert>
          <AlertTitle>Entreprise requise</AlertTitle>
          <AlertDescription>
            Sélectionnez une entreprise pour afficher les analytics RH.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const showInitialSkeleton = isLoading && !data;
  const evo = data?.absenteisme.evolution_vs_mois_precedent ?? 0;
  const evoNeutral = Math.abs(evo) < 0.05;
  const evoPositiveIsWorse = !evoNeutral && evo > 0;

  return (
    <div className="container max-w-7xl space-y-6 py-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Analytics RH</h1>
          <p className="text-muted-foreground text-sm">
            Turnover, démographie, absentéisme et répartition par service (
            {activeCompany?.company_name ?? "—"})
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => {
            void refetch();
            void refetchAnomalies();
            void refetchAudit();
          }}
          disabled={isFetching}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
          />
          Actualiser
        </Button>
      </div>

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
            Peu de mouvements ou d’effectifs renseignés sur la période : certains
            graphiques peuvent rester vides.
          </AlertDescription>
        </Alert>
      ) : null}

      {showInitialSkeleton ? (
        <div className="lg:grid lg:grid-cols-3 lg:gap-4 space-y-4 lg:space-y-0">
          <div className="min-w-0 space-y-4 lg:col-span-2">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <SectionSkeleton />
              <SectionSkeleton />
            </div>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              <SectionSkeleton />
              <SectionSkeleton />
            </div>
            <SectionSkeleton />
          </div>
          <div className="min-w-0 lg:col-span-1">
            <SectionSkeleton />
          </div>
        </div>
      ) : (
        <>
        <div className="lg:grid lg:grid-cols-3 lg:items-start lg:gap-4 space-y-4 lg:space-y-0">
          <div className="min-w-0 space-y-4 lg:col-span-2">
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {/* Turnover */}
              <Card>
                <CardHeader className="p-4 pb-0">
                  <SectionHeading
                    title="Turnover"
                    subtitle="Rolling 12 mois (effectif actuel comme base)"
                  />
                </CardHeader>
                <CardContent className="space-y-3 p-4 pt-2">
                  {data ? (
                    <>
                      <div className="flex flex-wrap items-end justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-muted-foreground text-xs">Taux annuel</p>
                          <p className="text-2xl font-bold tabular-nums leading-none">
                            {data.turnover.taux_turnover_annuel.toLocaleString("fr-FR", {
                              maximumFractionDigits: 1,
                            })}
                            %
                          </p>
                        </div>
                        {(() => {
                          const b = turnoverBadge(data.turnover.taux_turnover_annuel);
                          return (
                            <Badge className={b.className} variant="default">
                              {b.label}
                            </Badge>
                          );
                        })()}
                      </div>
                      <div className="text-muted-foreground grid grid-cols-2 gap-x-2 gap-y-1 text-xs">
                        <div className="truncate">
                          Emb. :{" "}
                          <span className="text-foreground font-medium">
                            {data.turnover.nb_embauches_12_mois}
                          </span>
                        </div>
                        <div className="truncate">
                          Dép. :{" "}
                          <span className="text-foreground font-medium">
                            {data.turnover.nb_departs_12_mois}
                          </span>
                        </div>
                      </div>
                      <div className="h-[220px] w-full min-w-0">
                        <ResponsiveContainer width="100%" height={220}>
                          <BarChart data={turnoverRatioBar} layout="vertical" margin={{ left: 4, right: 8, top: 4, bottom: 4 }}>
                            <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                            <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                            <YAxis type="category" dataKey="label" width={120} tick={{ fontSize: 10 }} />
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

              {/* Absentéisme */}
              <Card>
                <CardHeader className="p-4 pb-0">
                  <SectionHeading
                    title="Absentéisme"
                    subtitle="30 jours glissants vs mois précédent (même durée)"
                  />
                </CardHeader>
                <CardContent className="space-y-3 p-4 pt-2">
                  {data ? (
                    <>
                      <div className="flex flex-wrap items-end justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-muted-foreground text-xs">Taux global</p>
                          <p className="text-2xl font-bold tabular-nums leading-none">
                            {data.absenteisme.taux_global.toLocaleString("fr-FR", {
                              maximumFractionDigits: 2,
                            })}
                            %
                          </p>
                        </div>
                        <div
                          className={`flex min-w-0 shrink-0 items-center gap-1 text-xs font-medium ${
                            evoNeutral
                              ? "text-muted-foreground"
                              : evoPositiveIsWorse
                                ? "text-red-600"
                                : "text-emerald-600"
                          }`}
                        >
                          {!evoNeutral ? (
                            evoPositiveIsWorse ? (
                              <ArrowUpRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
                            ) : (
                              <ArrowDownRight className="h-3.5 w-3.5 shrink-0" aria-hidden />
                            )
                          ) : null}
                          <span className="truncate">
                            {evo > 0 ? "+" : ""}
                            {evo.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}% vs N-1
                          </span>
                        </div>
                      </div>
                      <div className="grid gap-1 text-xs">
                        <div className="flex justify-between gap-2">
                          <span>Maladie</span>
                          <span className="tabular-nums">
                            {data.absenteisme.taux_maladie.toFixed(1)}% ({data.absenteisme.jours_perdus_maladie} j.)
                          </span>
                        </div>
                        <div className="flex justify-between gap-2">
                          <span>AT</span>
                          <span className="tabular-nums">
                            {data.absenteisme.taux_at.toFixed(1)}% ({data.absenteisme.jours_perdus_at} j.)
                          </span>
                        </div>
                        <div className="flex justify-between gap-2">
                          <span>Autres</span>
                          <span className="tabular-nums">
                            {data.absenteisme.taux_autres.toFixed(1)}% ({data.absenteisme.jours_perdus_autres} j.)
                          </span>
                        </div>
                      </div>
                      <div className="bg-muted h-2.5 w-full overflow-hidden rounded-full">
                        <div className="flex h-full w-full">
                          <div
                            className="h-full bg-primary transition-all"
                            style={{ width: `${absStack.mal}%` }}
                            title="Maladie"
                          />
                          <div
                            className="h-full bg-primary/60"
                            style={{ width: `${absStack.at}%` }}
                            title="AT"
                          />
                          <div
                            className="h-full bg-muted-foreground/30"
                            style={{ width: `${absStack.aut}%` }}
                            title="Autres"
                          />
                        </div>
                      </div>
                    </>
                  ) : null}
                </CardContent>
              </Card>
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {/* Effectif par service */}
              <Card>
                <CardHeader className="p-4 pb-0">
                  <SectionHeading title="Effectif par service" />
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  {data && serviceChartData.length > 0 ? (
                    <div className="h-[220px] w-full min-w-0">
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={serviceChartData} margin={{ bottom: 48, left: 4, right: 8, top: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis
                            dataKey="service"
                            angle={-30}
                            textAnchor="end"
                            height={56}
                            interval={0}
                            tick={{ fontSize: 9 }}
                          />
                          <YAxis allowDecimals={false} tick={{ fontSize: 10 }} width={32} />
                          <RechartsTooltip />
                          <Bar dataKey="count" fill="hsl(var(--primary))" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-sm">Aucune répartition par service.</p>
                  )}
                </CardContent>
              </Card>

              {/* Masse salariale */}
              <Card>
                <CardHeader className="p-4 pb-0">
                  <SectionHeading
                    title="Masse salariale par service"
                    subtitle="Brut mensuel de base (salaire_de_base)"
                  />
                </CardHeader>
                <CardContent className="p-4 pt-2">
                  {data && masseChartData.length > 0 ? (
                    <div className="h-[220px] w-full min-w-0">
                      <ResponsiveContainer width="100%" height={220}>
                        <BarChart data={masseChartData} margin={{ bottom: 48, left: 4, right: 8, top: 4 }}>
                          <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                          <XAxis
                            dataKey="service"
                            angle={-30}
                            textAnchor="end"
                            height={56}
                            interval={0}
                            tick={{ fontSize: 9 }}
                          />
                          <YAxis
                            width={40}
                            tick={{ fontSize: 9 }}
                            tickFormatter={(v) =>
                              Number(v).toLocaleString("fr-FR", { maximumFractionDigits: 0 })
                            }
                          />
                          <RechartsTooltip formatter={(v: number) => [eur.format(v), "Masse brute"]} />
                          <Legend wrapperStyle={{ fontSize: 11 }} />
                          <Bar dataKey="masse" fill="hsl(var(--primary))" name="Masse" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  ) : (
                    <p className="text-muted-foreground text-sm">Aucune masse salariale par service.</p>
                  )}
                </CardContent>
              </Card>
            </div>
          </div>

          {/* Colonne droite : démographie */}
          <div className="min-w-0 space-y-4 lg:col-span-1">
            <Card>
              <CardHeader className="p-4 pb-0">
                <SectionHeading
                  title="Pyramide des âges"
                  subtitle="Salariés actifs avec date de naissance"
                />
              </CardHeader>
              <CardContent className="p-4 pt-2">
                {data ? (
                  <div className="space-y-2">
                    <div className="h-[220px] w-full min-w-0">
                      <ResponsiveContainer width="100%" height={220}>
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
                    <ul className="text-muted-foreground flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] leading-tight">
                      {data.pyramide_ages.map((p) => (
                        <li key={p.tranche} className="max-w-[9rem] truncate">
                          <span className="text-foreground font-medium">{p.tranche}</span>{" "}
                          {p.pourcentage.toLocaleString("fr-FR", { maximumFractionDigits: 1 })}%
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </CardContent>
            </Card>
          </div>
        </div>

        <div className="mt-4 space-y-4">
          {/* SECTION 6 — Anomalies paie */}
          <Card>
            <CardHeader className="p-4 pb-2">
              <SectionHeading
                title="Anomalies de paie détectées"
                subtitle="Contrôles automatiques sur les bulletins du mois sélectionné"
                right={
                  <div className="flex shrink-0 flex-col gap-1">
                    <Label
                      htmlFor="payroll-period"
                      className="text-xs leading-none text-muted-foreground"
                    >
                      Période
                    </Label>
                    <Input
                      id="payroll-period"
                      type="month"
                      value={payrollYm}
                      onChange={(e) => setPayrollYm(e.target.value)}
                      className="h-9 w-[9.5rem]"
                    />
                  </div>
                }
              />
            </CardHeader>
            <CardContent className="space-y-3 p-4 pt-0">
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
                        <p className="text-muted-foreground text-xs">Total bulletins</p>
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
                    <p className="text-muted-foreground text-sm">
                      ✅ Aucune anomalie détectée ce mois-ci
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
                            <TableHead>Valeur</TableHead>
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
                              <TableCell className="max-w-[200px] text-xs">
                                {row.message}
                              </TableCell>
                              <TableCell className="max-w-[120px] truncate text-xs">
                                {row.valeur_detectee}
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

          {/* SECTION 7 — Journal d'audit */}
          <Card>
            <CardHeader className="p-4 pb-2">
              <SectionHeading
                title="Journal d&apos;audit"
                subtitle="Actions sensibles enregistrées (best effort côté serveur)"
              />
            </CardHeader>
            <CardContent className="space-y-3 p-4 pt-0">
              <div className="mb-1 flex flex-wrap items-end gap-3">
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
                      <SelectItem value="employee">employee</SelectItem>
                      <SelectItem value="payslip">payslip</SelectItem>
                      <SelectItem value="absence_request">absence_request</SelectItem>
                      <SelectItem value="candidate">candidate</SelectItem>
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
                  <AlertTitle>Audit</AlertTitle>
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
                          <TableCell colSpan={5} className="text-muted-foreground px-3 py-2 text-center text-sm">
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
                              {row.resource_id ? ` / ${row.resource_id}` : ""}
                            </TableCell>
                            <TableCell className="max-w-[180px] truncate text-xs text-muted-foreground">
                              {row.details
                                ? JSON.stringify(row.details)
                                : "—"}
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
          </Card>

          {/* SECTION 8 — Webhooks & Intégrations BI */}
          <Card>
            <CardHeader className="p-4 pb-2">
              <SectionHeading
                title="Webhooks &amp; Intégrations BI"
                subtitle="Notifications HTTP et repères pour connecteurs analytiques"
              />
            </CardHeader>
            <CardContent className="space-y-6 p-4 pt-0">
              <div className="space-y-4">
                <h3 className="text-sm font-semibold tracking-tight">
                  Webhooks configurés
                </h3>
                {!canManageWebhooks ? (
                  <p className="text-muted-foreground text-sm">
                    Accès réservé aux profils RH pour gérer les webhooks.
                  </p>
                ) : whLoading ? (
                  <Skeleton className="h-24 w-full" />
                ) : (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <Button type="button" size="sm" onClick={() => setWhCreateOpen(true)}>
                        Ajouter un webhook
                      </Button>
                    </div>
                    {(webhooksData ?? []).length === 0 ? (
                      <p className="text-muted-foreground text-sm">
                        Aucun webhook. Ajoutez une URL pour recevoir les événements métier en
                        temps réel.
                      </p>
                    ) : (
                      <div className="space-y-4">
                        {(webhooksData ?? []).map((wh: WebhookConfig) => (
                          <div
                            key={wh.id}
                            className="flex flex-col gap-3 rounded-lg border p-4 sm:flex-row sm:items-start sm:justify-between"
                          >
                            <div className="min-w-0 flex-1 space-y-2">
                              <div className="flex flex-wrap items-center gap-2">
                                <span className="font-medium">{wh.name}</span>
                                <Badge variant={wh.is_active ? "default" : "secondary"}>
                                  {wh.is_active ? "Actif" : "Inactif"}
                                </Badge>
                              </div>
                              <p className="truncate text-xs text-muted-foreground" title={wh.url}>
                                {wh.url}
                              </p>
                              <div className="flex flex-wrap gap-1">
                                {wh.events.map((ev) => (
                                  <Badge key={ev} variant="outline" className="text-xs font-normal">
                                    {ev}
                                  </Badge>
                                ))}
                              </div>
                              <p className="text-muted-foreground text-xs">
                                Dernier envoi :{" "}
                                {wh.last_triggered_at
                                  ? new Date(wh.last_triggered_at).toLocaleString("fr-FR")
                                  : "—"}{" "}
                                · HTTP{" "}
                                {wh.last_status_code != null ? wh.last_status_code : "—"}
                              </p>
                            </div>
                            <div className="flex flex-wrap items-center gap-2 sm:flex-col sm:items-end">
                              <div className="flex items-center gap-2">
                                <span className="text-muted-foreground text-xs">Actif</span>
                                <Switch
                                  checked={wh.is_active}
                                  disabled={toggleWhMutation.isPending}
                                  onCheckedChange={(v) =>
                                    toggleWhMutation.mutate({ id: wh.id, is_active: Boolean(v) })
                                  }
                                  aria-label={`Activer le webhook ${wh.name}`}
                                />
                              </div>
                              <div className="flex flex-wrap gap-2">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  disabled={testWhMutation.isPending}
                                  onClick={() => testWhMutation.mutate(wh.id)}
                                >
                                  Tester
                                </Button>
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setLogsWhId(wh.id)}
                                >
                                  Logs
                                </Button>
                                <Button
                                  type="button"
                                  variant="destructive"
                                  size="sm"
                                  disabled={deleteWhMutation.isPending}
                                  onClick={() => {
                                    if (
                                      window.confirm(
                                        `Supprimer le webhook « ${wh.name} » ?`,
                                      )
                                    ) {
                                      deleteWhMutation.mutate(wh.id);
                                    }
                                  }}
                                >
                                  Supprimer
                                </Button>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="space-y-4">
                <h3 className="text-sm font-semibold tracking-tight">Connecteurs BI</h3>
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                  <Card className="border-muted">
                    <CardHeader className="space-y-1 p-3 pb-2">
                      <CardTitle className="text-sm font-semibold">Power BI</CardTitle>
                      <CardDescription className="line-clamp-2 text-xs">
                        API REST EYWAI
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2 p-3 pt-0 text-xs text-muted-foreground">
                      <p>
                        URL base :{" "}
                        <span className="font-mono text-xs text-foreground">
                          {typeof window !== "undefined" ? window.location.origin : ""}/api
                        </span>
                      </p>
                      <p>
                        Endpoint recommandé :{" "}
                        <span className="font-mono text-xs text-foreground">
                          /api/dashboard/analytics
                        </span>
                      </p>
                      <p>Auth : Bearer Token JWT</p>
                      <Button variant="outline" size="sm" className="mt-2 w-full" asChild>
                        <a href={openapiDocsUrl} target="_blank" rel="noopener noreferrer">
                          Voir la documentation
                        </a>
                      </Button>
                    </CardContent>
                  </Card>
                  <Card className="border-muted">
                    <CardHeader className="space-y-1 p-3 pb-2">
                      <CardTitle className="text-sm font-semibold">Tableau</CardTitle>
                      <CardDescription className="line-clamp-2 text-xs">
                        API REST EYWAI
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2 p-3 pt-0 text-xs text-muted-foreground">
                      <p>
                        URL base :{" "}
                        <span className="font-mono text-xs text-foreground">
                          {typeof window !== "undefined" ? window.location.origin : ""}/api
                        </span>
                      </p>
                      <p>
                        Endpoint recommandé :{" "}
                        <span className="font-mono text-xs text-foreground">
                          /api/exports/generate
                        </span>
                      </p>
                      <p>Auth : Bearer Token JWT</p>
                      <Button variant="outline" size="sm" className="mt-2 w-full" asChild>
                        <a href={openapiDocsUrl} target="_blank" rel="noopener noreferrer">
                          Voir la documentation
                        </a>
                      </Button>
                    </CardContent>
                  </Card>
                  <Card className="border-muted">
                    <CardHeader className="space-y-1 p-3 pb-2">
                      <CardTitle className="text-sm font-semibold">Metabase</CardTitle>
                      <CardDescription className="line-clamp-2 text-xs">
                        API REST EYWAI
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-2 p-3 pt-0 text-xs text-muted-foreground">
                      <p>
                        URL base :{" "}
                        <span className="font-mono text-xs text-foreground">
                          {typeof window !== "undefined" ? window.location.origin : ""}/api
                        </span>
                      </p>
                      <p>
                        Endpoint recommandé :{" "}
                        <span className="font-mono text-xs text-foreground">
                          /api/dashboard/all
                        </span>
                      </p>
                      <p>Auth : Bearer Token JWT</p>
                      <Button variant="outline" size="sm" className="mt-2 w-full" asChild>
                        <a href={openapiDocsUrl} target="_blank" rel="noopener noreferrer">
                          Voir la documentation
                        </a>
                      </Button>
                    </CardContent>
                  </Card>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

          <Dialog open={whCreateOpen} onOpenChange={setWhCreateOpen}>
            <DialogContent className="max-h-[90vh] overflow-y-auto sm:max-w-lg">
              <DialogHeader>
                <DialogTitle>Nouveau webhook</DialogTitle>
                <DialogDescription>
                  URL HTTPS recommandée. Secret optionnel pour signature HMAC (en-tête{" "}
                  <span className="font-mono">X-EYWAI-Signature</span>).
                </DialogDescription>
              </DialogHeader>
              <div className="grid gap-4 py-2">
                <div className="space-y-2">
                  <Label htmlFor="wh-name">Nom</Label>
                  <Input
                    id="wh-name"
                    value={whName}
                    onChange={(e) => setWhName(e.target.value)}
                    placeholder="Ex. Power BI — production"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wh-url">URL</Label>
                  <Input
                    id="wh-url"
                    value={whUrl}
                    onChange={(e) => setWhUrl(e.target.value)}
                    placeholder="https://…"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="wh-secret">Secret (optionnel)</Label>
                  <Input
                    id="wh-secret"
                    type="password"
                    value={whSecret}
                    onChange={(e) => setWhSecret(e.target.value)}
                    autoComplete="new-password"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Événements</Label>
                  <div className="grid max-h-48 gap-2 overflow-y-auto rounded-md border p-3">
                    {WEBHOOK_EVENTS.map((ev) => (
                      <label
                        key={ev}
                        className="flex cursor-pointer items-center gap-2 text-sm"
                      >
                        <Checkbox
                          checked={Boolean(whEventsPick[ev])}
                          onCheckedChange={(c) =>
                            setWhEventsPick((prev) => ({
                              ...prev,
                              [ev]: c === true,
                            }))
                          }
                        />
                        <span className="font-mono text-xs">{ev}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button type="button" variant="outline" onClick={() => setWhCreateOpen(false)}>
                  Annuler
                </Button>
                <Button
                  type="button"
                  disabled={
                    createWhMutation.isPending ||
                    !whName.trim() ||
                    !whUrl.trim() ||
                    !WEBHOOK_EVENTS.some((e) => whEventsPick[e])
                  }
                  onClick={() => createWhMutation.mutate()}
                >
                  {createWhMutation.isPending ? "Création…" : "Créer"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>

          <Sheet
            open={logsWhId !== null}
            onOpenChange={(open) => {
              if (!open) setLogsWhId(null);
            }}
          >
            <SheetContent className="w-full overflow-y-auto sm:max-w-lg">
              <SheetHeader>
                <SheetTitle>Logs webhook</SheetTitle>
                <SheetDescription>20 derniers envois enregistrés côté serveur.</SheetDescription>
              </SheetHeader>
              <div className="mt-6 space-y-3">
                {whLogsFetching ? (
                  <Skeleton className="h-32 w-full" />
                ) : (whLogsData ?? []).length === 0 ? (
                  <p className="text-muted-foreground text-sm">Aucun log.</p>
                ) : (
                  (whLogsData ?? []).map((log: WebhookLog) => (
                    <div key={log.id} className="rounded-md border p-3 text-xs">
                      <div className="font-mono text-[11px] text-muted-foreground">
                        {new Date(log.created_at).toLocaleString("fr-FR")}
                      </div>
                      <div className="mt-1 font-medium">{log.event_type}</div>
                      <div className="text-muted-foreground mt-1">
                        HTTP {log.response_status ?? "—"} · {log.duration_ms ?? "—"} ms
                      </div>
                    </div>
                  ))
                )}
              </div>
            </SheetContent>
          </Sheet>
        </>
      )}
    </div>
  );
}
