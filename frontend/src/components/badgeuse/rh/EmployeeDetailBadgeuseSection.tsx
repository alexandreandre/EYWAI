import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, RefreshCw } from "lucide-react";
import {
  getEmployeeBadgeQr,
  regenerateEmployeeBadge,
  getEmployeeDaysSummary,
  validateEmployeeDay,
  type DaySummary,
} from "@/api/badgeuse";
import { BadgeCardExport } from "@/components/badgeuse/rh/BadgeCardExport";
import { EmployeeBadgeuseDayDetail } from "@/components/badgeuse/rh/EmployeeBadgeuseDayDetail";
import { formatSecondsToHoursMinutes } from "@/lib/badgeuseFormat";
import {
  apiErrorDetail,
  isBadgeuseSchemaMissing,
  periodRangeLastDays,
  formatBadgeuseDate,
  dayStatusLabel,
  BADGEUSE_MIGRATION_FILE,
} from "@/lib/badgeuseApiUtils";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

type Props = {
  employeeId: string;
  companyId: string;
  employeeName: string;
  isForfaitJour?: boolean;
  isTabActive?: boolean;
};

type PeriodPreset = "7" | "30";

function DaysListSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

export function EmployeeDetailBadgeuseSection({
  employeeId,
  companyId,
  employeeName,
  isForfaitJour = false,
  isTabActive = true,
}: Props) {
  const queryClient = useQueryClient();
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [periodPreset, setPeriodPreset] = useState<PeriodPreset>("7");
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [validatingPeriod, setValidatingPeriod] = useState(false);

  const { from, to } = useMemo(
    () => periodRangeLastDays(periodPreset === "7" ? 7 : 30),
    [periodPreset]
  );

  const queriesEnabled = isTabActive && !!employeeId && !!companyId && !isForfaitJour;

  const {
    data: qr,
    isLoading: qrLoading,
    isError: qrError,
    error: qrQueryError,
    refetch: refetchQr,
  } = useQuery({
    queryKey: ["badgeuse", "employee-qr", employeeId, companyId],
    queryFn: () => getEmployeeBadgeQr(employeeId, companyId),
    enabled: queriesEnabled,
  });

  const {
    data: days,
    isLoading: daysLoading,
    isError: daysError,
    error: daysQueryError,
    refetch: refetchDays,
  } = useQuery({
    queryKey: ["badgeuse", "employee-days", companyId, employeeId, from, to],
    queryFn: () => getEmployeeDaysSummary(employeeId, companyId, from, to),
    enabled: queriesEnabled,
  });

  const qrErrorMessage = apiErrorDetail(qrQueryError, "Impossible de charger le badge QR.");
  const daysErrorMessage = apiErrorDetail(daysQueryError, "Impossible de charger l'historique.");
  const schemaMissing =
    isBadgeuseSchemaMissing(qrQueryError, qrErrorMessage) ||
    isBadgeuseSchemaMissing(daysQueryError, daysErrorMessage);

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateEmployeeBadge(employeeId, companyId),
    onSuccess: () => {
      toast.success("Nouveau QR généré — les anciennes cartes ne fonctionnent plus.");
      void queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-qr", employeeId, companyId],
      });
      setConfirmOpen(false);
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Échec de la régénération";
      toast.error(String(message));
    },
  });

  const validatePeriod = async () => {
    if (!days?.length) return;
    setValidatingPeriod(true);
    try {
      const unvalidated = days.filter((d) => !d.validated).map((d) => d.date);
      if (unvalidated.length === 0) {
        toast.info("Toutes les journées affichées sont déjà validées.");
        return;
      }
      await Promise.all(
        unvalidated.map((d) => validateEmployeeDay(employeeId, companyId, d))
      );
      toast.success(
        unvalidated.length === 1
          ? "Journée validée."
          : `${unvalidated.length} journées validées.`
      );
      void queryClient.invalidateQueries({
        queryKey: ["badgeuse", "employee-days", companyId, employeeId, from, to],
      });
      if (selectedDay) {
        void queryClient.invalidateQueries({
          queryKey: ["badgeuse", "employee-day-detail", companyId, employeeId, selectedDay],
        });
      }
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        "Validation impossible";
      toast.error(String(message));
    } finally {
      setValidatingPeriod(false);
    }
  };

  const badgeuseRhLink = `/badgeuse-rh?employee=${encodeURIComponent(employeeId)}&tab=corrections`;

  if (isForfaitJour) {
    return (
      <Card className="p-6">
        <Alert>
          <AlertTitle>Badgeuse non applicable</AlertTitle>
          <AlertDescription>
            Ce collaborateur est au forfait jours : le pointage badgeuse ne s&apos;applique pas
            à son contrat.
          </AlertDescription>
        </Alert>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {schemaMissing && (
        <Alert variant="destructive">
          <AlertTitle>Base de données badgeuse non configurée</AlertTitle>
          <AlertDescription className="space-y-2">
            <p>{qrErrorMessage || daysErrorMessage}</p>
            <p className="text-sm">
              Exécutez la migration{" "}
              <code className="rounded bg-muted px-1 py-0.5 text-xs">{BADGEUSE_MIGRATION_FILE}</code>{" "}
              dans Supabase, puis rechargez la page.
            </p>
          </AlertDescription>
        </Alert>
      )}

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">Badgeuse</h3>
          <p className="text-sm text-muted-foreground">
            Carte QR, historique et corrections pour {employeeName}
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          <Link to={badgeuseRhLink}>
            <ExternalLink className="h-4 w-4 mr-2" />
            Badgeuse entreprise
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
        <div className="space-y-4">
          <Card className="p-4 space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold">Carte badge</h4>
              <AlertDialog open={confirmOpen} onOpenChange={setConfirmOpen}>
                <AlertDialogTrigger asChild>
                  <Button variant="outline" size="sm" type="button">
                    Régénérer le QR
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Régénérer le badge ?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Les cartes et QR actuels de {employeeName} ne fonctionneront plus.
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Annuler</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={() => regenerateMutation.mutate()}
                      disabled={regenerateMutation.isPending}
                    >
                      Confirmer
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>

            {qrLoading && (
              <div className="space-y-2">
                <Skeleton className="h-[220px] w-[220px]" />
                <Skeleton className="h-4 w-32" />
              </div>
            )}
            {qrError && !schemaMissing && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 space-y-3">
                <p className="text-sm text-destructive">{qrErrorMessage}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => void refetchQr()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Réessayer
                </Button>
              </div>
            )}
            {!qrLoading && !qrError && qr?.qr_payload && (
              <BadgeCardExport
                qrPayload={qr.qr_payload}
                displayName={qr.employee_display_name || employeeName}
                username={qr.badge_username}
              />
            )}
            {!qrLoading && !qrError && !qr?.qr_payload && (
              <p className="text-sm text-muted-foreground">Aucun badge disponible.</p>
            )}
          </Card>

          <Card className="p-4 space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <h4 className="text-sm font-semibold">Historique</h4>
              <ToggleGroup
                type="single"
                value={periodPreset}
                onValueChange={(v) => {
                  if (v === "7" || v === "30") {
                    setPeriodPreset(v);
                    setSelectedDay(null);
                  }
                }}
                size="sm"
              >
                <ToggleGroupItem value="7" aria-label="7 derniers jours">
                  7 jours
                </ToggleGroupItem>
                <ToggleGroupItem value="30" aria-label="30 derniers jours">
                  30 jours
                </ToggleGroupItem>
              </ToggleGroup>
            </div>

            {daysLoading && <DaysListSkeleton />}
            {daysError && !schemaMissing && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-4 space-y-3">
                <p className="text-sm text-destructive">{daysErrorMessage}</p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => void refetchDays()}
                >
                  <RefreshCw className="h-4 w-4" />
                  Réessayer
                </Button>
              </div>
            )}
            {!daysLoading && !daysError && (!days || days.length === 0) && (
              <p className="text-sm text-muted-foreground">Aucun pointage sur la période.</p>
            )}
            {!daysLoading && !daysError && days && days.length > 0 && (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs text-muted-foreground">
                    {formatBadgeuseDate(from)} — {formatBadgeuseDate(to)}
                  </span>
                  <Button
                    size="xs"
                    variant="outline"
                    type="button"
                    onClick={() => void validatePeriod()}
                    disabled={validatingPeriod}
                  >
                    {validatingPeriod ? "Validation…" : "Valider la période"}
                  </Button>
                </div>
                <div className="space-y-2 max-h-72 overflow-y-auto">
                  {days.map((d) => (
                    <DayRow
                      key={d.date}
                      day={d}
                      selected={selectedDay === d.date}
                      onSelect={() => setSelectedDay(d.date)}
                    />
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>

        <Card className="p-4">
          <EmployeeBadgeuseDayDetail
            employeeId={employeeId}
            companyId={companyId}
            day={selectedDay}
            periodFrom={from}
            periodTo={to}
          />
        </Card>
      </div>
    </div>
  );
}

function DayRow({
  day,
  selected,
  onSelect,
}: {
  day: DaySummary;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "w-full flex flex-col gap-1 rounded-md border px-3 py-2 text-left text-sm transition-colors sm:flex-row sm:items-center sm:justify-between",
        selected ? "border-primary bg-primary/10 ring-1 ring-primary" : "hover:bg-muted/60"
      )}
    >
      <span className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{formatBadgeuseDate(day.date)}</span>
        <span className="text-muted-foreground">{dayStatusLabel(day.status)}</span>
        {day.validated && (
          <Badge variant="outline" className="text-xs border-emerald-300 text-emerald-800">
            Validé
          </Badge>
        )}
        {day.has_anomalies && (
          <Badge variant="outline" className="text-xs border-amber-300 text-amber-800">
            Anomalie
          </Badge>
        )}
      </span>
      <span className="tabular-nums text-xs text-muted-foreground">
        {formatSecondsToHoursMinutes(day.total_seconds)}
      </span>
    </button>
  );
}
