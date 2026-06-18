import { RhPageHeader } from '@/components/layout';
import { useState, useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Download, RefreshCw, Trash2, UserX, Users, CalendarSync } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import {
  getCompanyBadgeuseSummary,
  getEmployeeDaysSummary,
  deleteBadgeuseEvent,
  validateEmployeeDay,
  exportBadgeuseCsvUrl,
  getBadgeuseDashboardToday,
  getBadgeuseSettings,
  updateBadgeuseSettings,
  DaySummary,
} from "@/api/badgeuse";
import { importActualHoursFromBadgeuse } from "@/api/calendar";
import { formatSecondsToHoursMinutes, formatTimeFr, eventTypeLabel, sourceLabel } from "@/lib/badgeuseFormat";
import { apiErrorDetail, isBadgeuseSchemaMissing, BADGEUSE_MIGRATION_FILE } from "@/lib/badgeuseApiUtils";
import { EmployeeBadgeuseDayDetail } from "@/components/badgeuse/rh/EmployeeBadgeuseDayDetail";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Switch } from "@/components/ui/switch";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { toast } from "sonner";
import { QrScannerPanel } from "@/components/badgeuse/rh/QrScannerPanel";
import { BadgeuseFallbackPanel } from "@/components/badgeuse/rh/BadgeuseFallbackPanel";
import { BadgeuseTerminalDevicesPanel } from "@/components/badgeuse/rh/BadgeuseTerminalDevicesPanel";
import { BadgeuseOpenOnDeviceButton } from "@/components/badgeuse/rh/BadgeuseOpenOnDeviceButton";

function secondsToHoursLabel(totalSeconds: number): string {
  return formatSecondsToHoursMinutes(totalSeconds);
}

function startOfWeekIso(d: Date): string {
  const day = d.getDay();
  const diff = d.getDate() - day + (day === 0 ? -6 : 1);
  const monday = new Date(d);
  monday.setDate(diff);
  return monday.toISOString().slice(0, 10);
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

function detectPeriodPreset(from: string, to: string): string {
  const today = todayIso();
  if (from === to && from === today) {
    return "today";
  }
  if (to === today && from === startOfWeekIso(new Date())) {
    return "week";
  }
  return "";
}

export default function BadgeuseRhPage() {
  const { activeCompany } = useCompany();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const [from, setFrom] = useState<string>(todayIso());
  const [to, setTo] = useState<string>(todayIso());
  const [periodPreset, setPeriodPreset] = useState<string>("today");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(
    () => searchParams.get("employee")
  );
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [validatingWeek, setValidatingWeek] = useState(false);
  const [importingCalendar, setImportingCalendar] = useState(false);
  const [activeTab, setActiveTab] = useState(() => {
    const tab = searchParams.get("tab");
    if (tab === "corrections" || tab === "settings") return tab;
    return "overview";
  });

  const companyId = activeCompany?.company_id;

  useEffect(() => {
    const emp = searchParams.get("employee");
    const tab = searchParams.get("tab");
    if (emp) setSelectedEmployeeId(emp);
    if (tab === "corrections" || tab === "overview" || tab === "settings") {
      setActiveTab(tab);
    }
  }, [searchParams]);

  const invalidateBadgeuseRealtime = () => {
    queryClient.invalidateQueries({ queryKey: ["badgeuse", "dashboard-today", companyId] });
    queryClient.invalidateQueries({ queryKey: ["badgeuse", "punch-candidates", companyId] });
    queryClient.invalidateQueries({ queryKey: ["badgeuse", "summary"] });
  };

  const {
    data: dashboard,
    isError: dashboardError,
    error: dashboardQueryError,
    refetch: refetchDashboard,
    isLoading: dashboardLoading,
  } = useQuery({
    queryKey: ["badgeuse", "dashboard-today", companyId],
    queryFn: () => getBadgeuseDashboardToday(companyId as string),
    enabled: !!companyId,
  });

  const { data: badgeSettings } = useQuery({
    queryKey: ["badgeuse", "settings", companyId],
    queryFn: () => getBadgeuseSettings(companyId as string),
    enabled: !!companyId,
  });

  const settingsMutation = useMutation({
    mutationFn: (patch: { allow_self_toggle?: boolean; scan_mode_enabled?: boolean }) =>
      updateBadgeuseSettings(companyId as string, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["badgeuse", "settings", companyId] });
    },
  });

  const {
    data,
    isLoading,
    isError,
    error: summaryError,
    refetch: refetchSummary,
  } = useQuery({
    queryKey: ["badgeuse", "summary", companyId, from, to],
    queryFn: () =>
      getCompanyBadgeuseSummary(companyId as string, from, to, false),
    enabled: !!companyId,
  });

  const summaryErrorMessage = apiErrorDetail(
    summaryError,
    "Erreur lors du chargement de la synthèse.",
  );
  const dashboardErrorMessage = apiErrorDetail(
    dashboardQueryError,
    "Impossible de charger le tableau de bord du jour."
  );
  const summarySchemaMissing = isBadgeuseSchemaMissing(summaryError, summaryErrorMessage);

  const { data: employeeDays } = useQuery<DaySummary[] | undefined>({
    queryKey: ["badgeuse", "employee-days", companyId, selectedEmployeeId, from, to],
    queryFn: () =>
      getEmployeeDaysSummary(
        selectedEmployeeId as string,
        companyId as string,
        from,
        to
      ),
    enabled: !!companyId && !!selectedEmployeeId,
  });

  const deleteRecentScanMutation = useMutation({
    mutationFn: (eventId: string) => deleteBadgeuseEvent(eventId, companyId as string),
    onSuccess: () => {
      invalidateBadgeuseRealtime();
      if (selectedEmployeeId) {
        queryClient.invalidateQueries({
          queryKey: ["badgeuse", "employee-days", companyId, selectedEmployeeId, from, to],
        });
      }
      if (selectedEmployeeId && selectedDay) {
        queryClient.invalidateQueries({
          queryKey: ["badgeuse", "employee-day-detail", companyId, selectedEmployeeId, selectedDay],
        });
      }
    },
  });

  const validateWeek = async () => {
    if (!employeeDays || !selectedEmployeeId) return;
    setValidatingWeek(true);
    try {
      const daysToValidate = employeeDays.map((d) => d.date);
      await Promise.all(
        daysToValidate.map((d) =>
          validateEmployeeDay(selectedEmployeeId as string, companyId as string, d)
        )
      );
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["badgeuse", "employee-day-detail", companyId, selectedEmployeeId, selectedDay],
        }),
        queryClient.invalidateQueries({
          queryKey: ["badgeuse", "employee-days", companyId, selectedEmployeeId, from, to],
        }),
      ]);
    } finally {
      setValidatingWeek(false);
    }
  };

  if (!companyId) {
    return <div>Aucune entreprise active sélectionnée.</div>;
  }

  const totalTeamSeconds =
    data?.reduce((acc, row) => acc + row.total_effective_seconds, 0) ?? 0;
  const totalTeamBrutSeconds =
    data?.reduce((acc, row) => acc + row.total_seconds, 0) ?? 0;
  const anomalyEmployees = data?.filter((r) => r.days_with_anomalies > 0).length ?? 0;

  const importPeriodMonth = () => {
    const ref = to || from;
    const d = new Date(ref);
    return { year: d.getFullYear(), month: d.getMonth() + 1 };
  };

  const applyToCalendar = async () => {
    if (!selectedEmployeeId || !companyId) return;
    const { year, month } = importPeriodMonth();
    setImportingCalendar(true);
    try {
      const res = await importActualHoursFromBadgeuse(selectedEmployeeId, year, month);
      const payload = res.data;
      toast.success(
        `${payload.days_updated} jour(s) importé(s) vers le calendrier paie (${month}/${year}).`
      );
      if (payload.warnings?.length) {
        payload.warnings.forEach((w) => toast.message(w));
      }
    } catch (err) {
      toast.error(apiErrorDetail(err, "Impossible d'appliquer au calendrier."));
    } finally {
      setImportingCalendar(false);
    }
  };

  return (
    <div className="space-y-4">
      {summarySchemaMissing && (
        <Alert variant="destructive">
          <AlertTitle>Base de données badgeuse non configurée</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{summaryErrorMessage}</p>
            <p className="text-sm">
              Ouvrez le SQL Editor Supabase, exécutez le fichier{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">
                {BADGEUSE_MIGRATION_FILE}
              </code>
              , puis rechargez cette page.
            </p>
          </AlertDescription>
        </Alert>
      )}
      <RhPageHeader
        title="Badgeuse"
        description="Scan, secours sans QR et pilotage des pointages"
        actions={
          companyId ? <BadgeuseOpenOnDeviceButton companyId={companyId} /> : null
        }
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="overview">Vue d&apos;ensemble</TabsTrigger>
          <TabsTrigger value="corrections">Corrections</TabsTrigger>
          <TabsTrigger value="settings">Paramètres</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4 mt-4">
      <div className="grid grid-cols-1 lg:grid-cols-[1.25fr_380px] gap-4">
        <Card className="overflow-hidden">
          <div className="p-4 pb-0">
            <QrScannerPanel companyId={companyId} onScanSuccess={invalidateBadgeuseRealtime} />
          </div>
          <div className="border-t bg-muted/15 p-4">
            <BadgeuseFallbackPanel companyId={companyId} onSuccess={invalidateBadgeuseRealtime} />
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-4 space-y-3">
            <p className="text-xs font-medium uppercase text-muted-foreground tracking-wide">
              Aujourd&apos;hui
            </p>
            {dashboardError ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center">
                <p className="text-sm text-destructive">{dashboardErrorMessage}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-3 gap-2"
                  onClick={() => void refetchDashboard()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Réessayer
                </Button>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3">
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <Users className="h-5 w-5 text-emerald-600" />
                  <div>
                    <p className="text-2xl font-bold tabular-nums">
                      {dashboardLoading ? "…" : (dashboard?.present_count ?? "—")}
                    </p>
                    <p className="text-xs text-muted-foreground">En présence</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <UserX className="h-5 w-5 text-slate-500" />
                  <div>
                    <p className="text-2xl font-bold tabular-nums">
                      {dashboardLoading ? "…" : (dashboard?.not_badged_count ?? "—")}
                    </p>
                    <p className="text-xs text-muted-foreground">Pas encore badgés</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <AlertTriangle className="h-5 w-5 text-amber-600" />
                  <div>
                    <p className="text-2xl font-bold tabular-nums">
                      {dashboardLoading ? "…" : (dashboard?.anomaly_count ?? "—")}
                    </p>
                    <p className="text-xs text-muted-foreground">Anomalies</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-lg border p-3">
                  <Download className="h-5 w-5 text-muted-foreground" />
                  <div>
                    <p className="text-2xl font-bold tabular-nums">{secondsToHoursLabel(totalTeamSeconds)}</p>
                    <p className="text-xs text-muted-foreground">
                      Heures comptabilisées (brut {secondsToHoursLabel(totalTeamBrutSeconds)})
                    </p>
                  </div>
                </div>
              </div>
            )}
          </Card>

          <Card className="p-4">
            <p className="text-sm font-semibold mb-3">Derniers scans</p>
            {dashboardError ? (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3 text-center">
                <p className="text-sm text-destructive">{dashboardErrorMessage}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="mt-2 gap-2"
                  onClick={() => void refetchDashboard()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Réessayer
                </Button>
              </div>
            ) : dashboardLoading ? (
              <p className="text-sm text-muted-foreground">Chargement…</p>
            ) : dashboard?.last_scans?.length ? (
              <ul className="space-y-2 text-sm">
                {dashboard.last_scans.map((s, i) => (
                  <li key={`${s.timestamp}-${i}`} className="flex items-center justify-between gap-2">
                    <div className="min-w-0">
                      <span className="truncate font-medium block">{s.employee_name}</span>
                      <span className="text-muted-foreground shrink-0 text-xs">
                        {eventTypeLabel(s.event_type)} {formatTimeFr(s.timestamp)}
                      </span>
                    </div>
                    <Button
                      type="button"
                      size="icon"
                      variant="ghost"
                      className="h-7 w-7 text-muted-foreground hover:text-destructive"
                      disabled={!s.id || deleteRecentScanMutation.isPending}
                      onClick={() => s.id && deleteRecentScanMutation.mutate(s.id)}
                      title="Supprimer ce pointage"
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted-foreground">Aucun scan pour le moment.</p>
            )}
          </Card>
        </div>
      </div>

      <Card className="p-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
          <ToggleGroup
            type="single"
            value={periodPreset}
            onValueChange={(value) => {
              if (!value) return;
              if (value === "today") {
                const t = todayIso();
                setFrom(t);
                setTo(t);
              } else if (value === "week") {
                const t = new Date();
                setFrom(startOfWeekIso(t));
                setTo(todayIso());
              }
              setPeriodPreset(value);
            }}
            className="w-full sm:w-auto"
          >
            <ToggleGroupItem value="today" className="flex-1 sm:flex-none">
              Aujourd&apos;hui
            </ToggleGroupItem>
            <ToggleGroupItem value="week" className="flex-1 sm:flex-none">
              Cette semaine
            </ToggleGroupItem>
          </ToggleGroup>

          <div className="flex flex-wrap items-center gap-2 sm:ml-auto">
            <Label htmlFor="badgeuse-from" className="sr-only">
              Du
            </Label>
            <Input
              id="badgeuse-from"
              type="date"
              value={from}
              max={to}
              className="h-9 w-[10.5rem] tabular-nums"
              onChange={(e) => {
                setFrom(e.target.value);
                setPeriodPreset(detectPeriodPreset(e.target.value, to));
              }}
            />
            <span className="text-sm text-muted-foreground">au</span>
            <Label htmlFor="badgeuse-to" className="sr-only">
              Au
            </Label>
            <Input
              id="badgeuse-to"
              type="date"
              value={to}
              min={from}
              className="h-9 w-[10.5rem] tabular-nums"
              onChange={(e) => {
                setTo(e.target.value);
                setPeriodPreset(detectPeriodPreset(from, e.target.value));
              }}
            />
          </div>

          <Button
            asChild
            variant="outline"
            size="sm"
            className="w-full sm:ml-0 sm:w-auto"
            disabled={!data || data.length === 0}
          >
            <a href={exportBadgeuseCsvUrl(companyId, from, to)}>
              <Download className="mr-2 h-4 w-4" aria-hidden />
              Export CSV
            </a>
          </Button>
        </div>
      </Card>

        <Card className="min-w-0 p-0">
          <div className="w-full overflow-x-auto">
            <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-2 text-left">Employé</th>
                <th className="px-4 py-2 text-left">Brut</th>
                <th className="px-4 py-2 text-left">Comptabilisé</th>
                <th className="px-4 py-2 text-left">Statut</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={4} className="px-4 py-3">
                    Chargement...
                  </td>
                </tr>
              )}
              {isError && (
                <tr>
                  <td colSpan={4} className="px-4 py-6">
                    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center">
                      <p className="text-sm text-destructive">{summaryErrorMessage}</p>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-3 gap-2"
                        onClick={() => void refetchSummary()}
                      >
                        <RefreshCw className="h-4 w-4" />
                        Réessayer
                      </Button>
                    </div>
                  </td>
                </tr>
              )}
              {!isLoading && !isError && data && data.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-3 text-muted-foreground">
                    Aucune donnée de badgeuse pour cette période.
                  </td>
                </tr>
              )}
              {!isLoading &&
                !isError &&
                data &&
                data.map((row) => (
                  <tr
                    key={row.employee_id}
                    className="border-t hover:bg-muted/50"
                  >
                    <td className="px-4 py-2">
                      {row.employee_name ?? row.employee_id}
                    </td>
                    <td className="px-4 py-2">
                      {secondsToHoursLabel(row.total_seconds)}
                    </td>
                    <td className="px-4 py-2">
                      {secondsToHoursLabel(row.total_effective_seconds)}
                    </td>
                    <td className="px-4 py-2">
                      {row.days_with_anomalies > 0 ? (
                        <Badge variant="outline" className="border-amber-300 text-amber-800">
                          Anomalies détectées
                        </Badge>
                      ) : (
                        <Badge variant="outline">RAS</Badge>
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
          </div>
        </Card>
        {!isError && anomalyEmployees > 0 && (
          <p className="text-sm text-amber-800">
            {anomalyEmployees} employé(s) avec anomalies sur la période — ouvrez l&apos;onglet
            Corrections.
          </p>
        )}
        </TabsContent>

        <TabsContent value="corrections" className="mt-4">
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1.5fr] gap-4">
        <Card className="min-w-0 p-0">
          <div className="w-full overflow-x-auto">
            <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-2 text-left">Employé</th>
                <th className="px-4 py-2 text-left">Brut</th>
                <th className="px-4 py-2 text-left">Comptabilisé</th>
                <th className="px-4 py-2 text-left">Statut</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={4} className="px-4 py-3">Chargement...</td>
                </tr>
              )}
              {isError && (
                <tr>
                  <td colSpan={4} className="px-4 py-6">
                    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 text-center">
                      <p className="text-sm text-destructive">{summaryErrorMessage}</p>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="mt-3 gap-2"
                        onClick={() => void refetchSummary()}
                      >
                        <RefreshCw className="h-4 w-4" />
                        Réessayer
                      </Button>
                    </div>
                  </td>
                </tr>
              )}
              {!isLoading && !isError && data && data.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-3 text-muted-foreground">
                    Aucune donnée de badgeuse pour cette période.
                  </td>
                </tr>
              )}
              {!isLoading &&
                !isError &&
                data?.map((row) => (
                  <tr
                    key={row.employee_id}
                    className={`border-t cursor-pointer hover:bg-muted/50 ${
                      selectedEmployeeId === row.employee_id ? "bg-muted/70" : ""
                    }`}
                    onClick={() => {
                      setSelectedEmployeeId(row.employee_id);
                      setSelectedDay(null);
                    }}
                  >
                    <td className="px-4 py-2">{row.employee_name ?? row.employee_id}</td>
                    <td className="px-4 py-2">{secondsToHoursLabel(row.total_seconds)}</td>
                    <td className="px-4 py-2">
                      {secondsToHoursLabel(row.total_effective_seconds)}
                    </td>
                    <td className="px-4 py-2">
                      {row.days_with_anomalies > 0 ? "Anomalies" : "RAS"}
                    </td>
                  </tr>
                ))}
            </tbody>
            </table>
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-4 space-y-3">
            <h2 className="text-lg font-semibold">Détail par jour</h2>
            {!selectedEmployeeId && (
              <p className="text-sm text-muted-foreground">
                Sélectionnez un employé dans la liste pour afficher le détail de ses
                journées.
              </p>
            )}
            {selectedEmployeeId && !employeeDays && (
              <p className="text-sm text-muted-foreground">Chargement des journées...</p>
            )}
            {selectedEmployeeId && employeeDays && employeeDays.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Aucun pointage pour cet employé sur la période sélectionnée.
              </p>
            )}
            {selectedEmployeeId && employeeDays && employeeDays.length > 0 && (
              <div className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="text-sm text-muted-foreground">
                    Journées sur la période sélectionnée
                  </span>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      size="xs"
                      variant="secondary"
                      onClick={() => void applyToCalendar()}
                      disabled={importingCalendar}
                    >
                      <CalendarSync className="mr-1 h-3.5 w-3.5" />
                      {importingCalendar ? "Import…" : "Appliquer au calendrier"}
                    </Button>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={validateWeek}
                      disabled={validatingWeek}
                    >
                      {validatingWeek ? "Validation en cours..." : "Valider la semaine"}
                    </Button>
                  </div>
                </div>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {employeeDays.map((day) => (
                    <button
                      key={day.date}
                      type="button"
                      onClick={() => setSelectedDay(day.date)}
                      className={`w-full flex items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors ${
                        selectedDay === day.date
                          ? "bg-primary text-primary-foreground"
                          : "hover:bg-muted"
                      }`}
                    >
                      <span>
                        {day.date} — {day.status}
                        {day.validated && " (validé)"}
                      </span>
                      <span className="text-xs">
                        {secondsToHoursLabel(day.computed_seconds ?? day.total_seconds)}
                        {day.has_override &&
                          day.effective_seconds !== (day.computed_seconds ?? day.total_seconds) &&
                          ` → ${secondsToHoursLabel(day.effective_seconds)}`}
                        {" • "}
                        {day.has_anomalies ? "Anomalies" : "OK"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Card>

          <Card className="p-4 space-y-3">
            {selectedEmployeeId && companyId ? (
              <EmployeeBadgeuseDayDetail
                employeeId={selectedEmployeeId}
                companyId={companyId}
                day={selectedDay}
                periodFrom={from}
                periodTo={to}
                title="Détail d'une journée"
              />
            ) : (
              <>
                <h2 className="text-lg font-semibold">Détail d&apos;une journée</h2>
                <p className="text-sm text-muted-foreground">
                  Sélectionnez un employé puis un jour pour voir et corriger les pointages.
                </p>
              </>
            )}
          </Card>
        </div>
      </div>
        </TabsContent>

        <TabsContent value="settings" className="mt-4 space-y-4">
          {companyId ? <BadgeuseTerminalDevicesPanel companyId={companyId} /> : null}
          <Card className="p-6 space-y-6 max-w-lg">
            <h2 className="text-lg font-semibold">Paramètres badgeuse</h2>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium">Mode scan QR</p>
                <p className="text-xs text-muted-foreground">
                  Active la page scan pour les RH
                </p>
              </div>
              <Switch
                checked={badgeSettings?.scan_mode_enabled ?? true}
                onCheckedChange={(v) =>
                  settingsMutation.mutate({ scan_mode_enabled: v })
                }
              />
            </div>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm font-medium">Badgeage depuis le téléphone</p>
                <p className="text-xs text-muted-foreground">
                  Permet aux employés de badger sans QR (télétravail)
                </p>
              </div>
              <Switch
                checked={badgeSettings?.allow_self_toggle ?? true}
                onCheckedChange={(v) =>
                  settingsMutation.mutate({ allow_self_toggle: v })
                }
              />
            </div>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

