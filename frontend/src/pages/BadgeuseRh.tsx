import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { isAxiosError } from "axios";
import { AlertTriangle, Download, RefreshCw, Trash2, UserX, Users } from "lucide-react";
import { useCompany } from "@/contexts/CompanyContext";
import {
  getCompanyBadgeuseSummary,
  getEmployeeDaysSummary,
  getEmployeeDayDetail,
  addEmployeeDayEvent,
  updateBadgeuseEvent,
  deleteBadgeuseEvent,
  validateEmployeeDay,
  exportBadgeuseCsvUrl,
  getBadgeuseDashboardToday,
  getBadgeuseSettings,
  updateBadgeuseSettings,
  DaySummary,
  DayDetail,
} from "@/api/badgeuse";
import { formatSecondsToHoursMinutes, formatTimeFr, eventTypeLabel, sourceLabel } from "@/lib/badgeuseFormat";
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
import { QrScannerPanel } from "@/components/badgeuse/rh/QrScannerPanel";
import { BadgeuseFallbackPanel } from "@/components/badgeuse/rh/BadgeuseFallbackPanel";

function apiErrorDetail(error: unknown, fallback: string): string {
  if (isAxiosError(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (error.response?.status === 503) {
      return "Service temporairement indisponible. Réessayez dans quelques secondes.";
    }
  }
  return fallback;
}

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
  const [from, setFrom] = useState<string>(todayIso());
  const [to, setTo] = useState<string>(todayIso());
  const [periodPreset, setPeriodPreset] = useState<string>("today");
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [newEventType, setNewEventType] = useState<"ENTREE" | "SORTIE">("ENTREE");
  const [newEventTime, setNewEventTime] = useState<string>("09:00");
  const [editEventId, setEditEventId] = useState<string | null>(null);
  const [editEventTime, setEditEventTime] = useState<string>("");
  const [editEventType, setEditEventType] = useState<"ENTREE" | "SORTIE">("ENTREE");
  const [validatingWeek, setValidatingWeek] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");

  const companyId = activeCompany?.company_id;

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
  const summarySchemaMissing =
    isAxiosError(summaryError) &&
    summaryError.response?.status === 503 &&
    summaryErrorMessage.toLowerCase().includes("tables badgeuse");

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

  const { data: dayDetail } = useQuery<DayDetail | undefined>({
    queryKey: ["badgeuse", "employee-day-detail", companyId, selectedEmployeeId, selectedDay],
    queryFn: () =>
      getEmployeeDayDetail(
        selectedEmployeeId as string,
        companyId as string,
        selectedDay as string
      ),
    enabled: !!companyId && !!selectedEmployeeId && !!selectedDay,
  });

  const addEventMutation = useMutation({
    mutationFn: () =>
      addEmployeeDayEvent(
        selectedEmployeeId as string,
        companyId as string,
        selectedDay as string,
        { event_type: newEventType, time: newEventTime }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-day-detail", companyId, selectedEmployeeId, selectedDay],
      });
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-days", companyId, selectedEmployeeId, from, to],
      });
    },
  });

  const updateEventMutation = useMutation({
    mutationFn: () =>
      updateBadgeuseEvent(editEventId as string, companyId as string, {
        time: editEventTime,
        event_type: editEventType,
        date: selectedDay as string,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-day-detail", companyId, selectedEmployeeId, selectedDay],
      });
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-days", companyId, selectedEmployeeId, from, to],
      });
      setEditEventId(null);
    },
  });

  const deleteEventMutation = useMutation({
    mutationFn: (eventId: string) =>
      deleteBadgeuseEvent(eventId, companyId as string),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-day-detail", companyId, selectedEmployeeId, selectedDay],
      });
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-days", companyId, selectedEmployeeId, from, to],
      });
    },
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

  const validateDayMutation = useMutation({
    mutationFn: () =>
      validateEmployeeDay(
        selectedEmployeeId as string,
        companyId as string,
        selectedDay as string
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-day-detail", companyId, selectedEmployeeId, selectedDay],
      });
      queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-days", companyId, selectedEmployeeId, from, to],
      });
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
    data?.reduce((acc, row) => acc + row.total_seconds, 0) ?? 0;
  const anomalyEmployees = data?.filter((r) => r.days_with_anomalies > 0).length ?? 0;

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
                supabase/migrations/20260525120000_badgeuse_qr.sql
              </code>
              , puis rechargez cette page.
            </p>
          </AlertDescription>
        </Alert>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Badgeuse</h1>
          <p className="text-sm text-muted-foreground">
            Scan, secours sans QR et pilotage des pointages
          </p>
        </div>
      </div>

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
                    <p className="text-xs text-muted-foreground">Heures période</p>
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
                <th className="px-4 py-2 text-left">Total heures</th>
                <th className="px-4 py-2 text-left">Statut</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={3} className="px-4 py-3">
                    Chargement...
                  </td>
                </tr>
              )}
              {isError && (
                <tr>
                  <td colSpan={3} className="px-4 py-6">
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
                  <td colSpan={3} className="px-4 py-3 text-muted-foreground">
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
                <th className="px-4 py-2 text-left">Total heures</th>
                <th className="px-4 py-2 text-left">Statut</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr>
                  <td colSpan={3} className="px-4 py-3">Chargement...</td>
                </tr>
              )}
              {isError && (
                <tr>
                  <td colSpan={3} className="px-4 py-6">
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
                  <td colSpan={3} className="px-4 py-3 text-muted-foreground">
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
                <div className="flex items-center justify-between">
                  <span className="text-sm text-muted-foreground">
                    Journées sur la période sélectionnée
                  </span>
                  <Button
                    size="xs"
                    variant="outline"
                    onClick={validateWeek}
                    disabled={validatingWeek}
                  >
                    {validatingWeek ? "Validation en cours..." : "Valider la semaine"}
                  </Button>
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
                        {secondsToHoursLabel(day.total_seconds)} •{" "}
                        {day.has_anomalies ? "Anomalies" : "OK"}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Card>

          <Card className="p-4 space-y-3">
            <h2 className="text-lg font-semibold">Détail d&apos;une journée</h2>
            {!selectedEmployeeId || !selectedDay ? (
              <p className="text-sm text-muted-foreground">
                Sélectionnez un jour pour voir et corriger les événements de pointage.
              </p>
            ) : !dayDetail ? (
              <p className="text-sm text-muted-foreground">
                Chargement du détail de la journée...
              </p>
            ) : (
              <div className="space-y-3">
                <div className="text-sm space-y-1">
                  <div className="font-medium">
                    Date : {dayDetail.date} — Statut : {dayDetail.status}
                  </div>
                  {dayDetail.validated && (
                    <div className="text-xs inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700 border border-emerald-200">
                      Journée validée par un RH
                    </div>
                  )}
                  <div className="text-muted-foreground">
                    Temps de présence : {secondsToHoursLabel(dayDetail.total_seconds)}
                  </div>
                </div>

                {dayDetail.anomalies.length > 0 && (
                  <div className="rounded-md bg-amber-50 border border-amber-200 p-2 text-xs text-amber-900 space-y-1">
                    <div className="font-semibold">Anomalies détectées :</div>
                    <ul className="list-disc list-inside space-y-0.5">
                      {dayDetail.anomalies.map((a) => (
                        <li key={a}>{a}</li>
                      ))}
                    </ul>
                  </div>
                )}

                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">Événements</span>
                  </div>
                  {dayDetail.events.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Aucun événement pour cette journée.
                    </p>
                  ) : (
                    <ul className="space-y-1 text-sm">
                      {dayDetail.events.map((e) => {
                        const time = new Date(e.timestamp).toLocaleTimeString("fr-FR", {
                          hour: "2-digit",
                          minute: "2-digit",
                        });
                        const isEditing = editEventId === (e.id ?? "");
                        return (
                          <li
                            key={e.id ?? e.timestamp}
                            className="flex items-center justify-between gap-2"
                          >
                            {!isEditing ? (
                              <>
                                <span>
                                  {e.event_type === "ENTREE" ? "Entrée" : "Sortie"} à {time}{" "}
                                  ({sourceLabel(e.source)})
                                </span>
                                <div className="flex gap-1">
                                  <Button
                                    size="xs"
                                    variant="outline"
                                    onClick={() => {
                                      const d = new Date(e.timestamp);
                                      const hh = d.getHours().toString().padStart(2, "0");
                                      const mm = d.getMinutes().toString().padStart(2, "0");
                                      setEditEventId(e.id ?? "");
                                      setEditEventTime(`${hh}:${mm}`);
                                      setEditEventType(e.event_type);
                                    }}
                                  >
                                    Modifier
                                  </Button>
                                  {e.id && (
                                    <Button
                                      size="xs"
                                      variant="ghost"
                                      className="text-red-600"
                                      onClick={() =>
                                        deleteEventMutation.mutate(e.id as string)
                                      }
                                    >
                                      Supprimer
                                    </Button>
                                  )}
                                </div>
                              </>
                            ) : (
                              <div className="w-full flex items-center gap-2">
                                <Select
                                  value={editEventType}
                                  onValueChange={(v) =>
                                    setEditEventType(v as "ENTREE" | "SORTIE")
                                  }
                                >
                                  <SelectTrigger className="w-28">
                                    <SelectValue placeholder="Type" />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="ENTREE">Entrée</SelectItem>
                                    <SelectItem value="SORTIE">Sortie</SelectItem>
                                  </SelectContent>
                                </Select>
                                <Input
                                  type="time"
                                  value={editEventTime}
                                  onChange={(ev) => setEditEventTime(ev.target.value)}
                                  className="w-28"
                                />
                                <div className="flex gap-1 ml-auto">
                                  <Button
                                    size="xs"
                                    variant="outline"
                                    onClick={() => updateEventMutation.mutate()}
                                    disabled={updateEventMutation.isLoading}
                                  >
                                    Enregistrer
                                  </Button>
                                  <Button
                                    size="xs"
                                    variant="ghost"
                                    onClick={() => setEditEventId(null)}
                                  >
                                    Annuler
                                  </Button>
                                </div>
                              </div>
                            )}
                          </li>
                        );
                      })}
                    </ul>
                  )}
                </div>

                <div className="border-t pt-3 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium">Ajouter un événement</div>
                    <Button
                      size="xs"
                      variant="outline"
                      onClick={() => validateDayMutation.mutate()}
                      disabled={validateDayMutation.isLoading}
                    >
                      {validateDayMutation.isLoading
                        ? "Validation..."
                        : "Valider la journée"}
                    </Button>
                  </div>
                  <div className="flex flex-wrap items-end gap-2">
                    <div className="flex flex-col">
                      <Label className="text-xs mb-1">Type</Label>
                      <Select
                        value={newEventType}
                        onValueChange={(v) =>
                          setNewEventType(v as "ENTREE" | "SORTIE")
                        }
                      >
                        <SelectTrigger className="w-32">
                          <SelectValue placeholder="Type" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="ENTREE">Entrée</SelectItem>
                          <SelectItem value="SORTIE">Sortie</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="flex flex-col">
                      <Label className="text-xs mb-1">Heure</Label>
                      <Input
                        type="time"
                        value={newEventTime}
                        onChange={(e) => setNewEventTime(e.target.value)}
                        className="w-28"
                      />
                    </div>
                    <Button
                      className="ml-auto"
                      size="sm"
                      onClick={() => addEventMutation.mutate()}
                      disabled={addEventMutation.isLoading}
                    >
                      {addEventMutation.isLoading
                        ? "Enregistrement..."
                        : "Ajouter l'événement"}
                    </Button>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
        </TabsContent>

        <TabsContent value="settings" className="mt-4">
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

