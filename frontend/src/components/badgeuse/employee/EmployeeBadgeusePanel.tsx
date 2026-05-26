import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Maximize2, ScanLine } from "lucide-react";
import {
  getMyBadgeuseStatusToday,
  toggleMyBadge,
} from "@/api/badgeuse";
import { BadgeQrDisplay } from "@/components/badgeuse/BadgeQrDisplay";
import { BadgeuseDayTimeline } from "@/components/badgeuse/employee/BadgeuseDayTimeline";
import { formatSecondsToHoursMinutes } from "@/lib/badgeuseFormat";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogTrigger,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

const todayIso = () => new Date().toISOString().slice(0, 10);

export function EmployeeBadgeusePanel() {
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState(todayIso);
  const [error, setError] = useState<string | null>(null);
  const isToday = selectedDate === todayIso();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["badgeuse", "status-today", selectedDate],
    queryFn: () => getMyBadgeuseStatusToday(selectedDate),
  });

  const mutation = useMutation({
    mutationFn: toggleMyBadge,
    onSuccess: (newStatus) => {
      queryClient.setQueryData(["badgeuse", "status-today", todayIso()], newStatus);
      queryClient.invalidateQueries({ queryKey: ["badgeuse", "status-today", selectedDate] });
      setError(null);
    },
    onError: (err: unknown) => {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ||
        (err as Error)?.message ||
        "Une erreur est survenue lors du badgeage.";
      setError(String(message));
    },
  });

  if (isLoading) {
    return <p className="text-sm text-muted-foreground">Chargement de la badgeuse…</p>;
  }

  if (isError || !data) {
    return <p className="text-sm text-red-600">Impossible de charger la badgeuse.</p>;
  }

  if (!data.is_eligible_for_badgeuse) {
    return (
      <Card className="p-6 space-y-2">
        <h1 className="text-xl font-semibold">Ma badgeuse</h1>
        <p className="text-sm text-muted-foreground">
          {data.reason || "La badgeuse n'est pas applicable à votre profil."}
        </p>
      </Card>
    );
  }

  const totalLabel = formatSecondsToHoursMinutes(data.total_seconds);
  const inPresence = data.next_action === "SORTIE";
  const showToggle = isToday && (data.allow_self_toggle !== false);

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold tracking-tight flex items-center gap-2">
            <ScanLine className="h-5 w-5 text-primary" />
            Ma badgeuse
          </h1>
          <p className="text-sm text-muted-foreground mt-1">{data.status_label}</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          <span className="text-xs text-muted-foreground">Date</span>
          <input
            type="date"
            value={selectedDate}
            onChange={(e) => setSelectedDate(e.target.value)}
            className="border rounded-md px-2 py-1 text-xs"
          />
        </div>
      </div>

      {data.anomalies && data.anomalies.length > 0 && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
          <p className="font-medium">Anomalie détectée</p>
          <ul className="mt-1 list-disc pl-4">
            {data.anomalies.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <Card className="p-6">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Temps travaillé
            </p>
            <p className="text-4xl font-bold tabular-nums tracking-tight mt-1">
              {totalLabel}
            </p>
          </div>
          <Badge
            variant="outline"
            className={cn(
              "text-sm px-3 py-1",
              inPresence
                ? "border-emerald-300 bg-emerald-50 text-emerald-800"
                : "border-slate-200 bg-slate-50"
            )}
          >
            {inPresence ? "En présence" : "Hors site"}
          </Badge>
        </div>
      </Card>

      {isToday && data.qr_payload && (
        <Card className="p-6 flex flex-col items-center">
          <Dialog>
            <div className="relative">
              <BadgeQrDisplay
                payload={data.qr_payload}
                displayName={data.employee_display_name}
                username={data.badge_username}
                size={180}
              />
              <DialogTrigger asChild>
                <Button
                  size="icon"
                  variant="secondary"
                  className="absolute top-2 right-2 h-8 w-8"
                  type="button"
                  title="Afficher en plein écran"
                >
                  <Maximize2 className="h-4 w-4" />
                </Button>
              </DialogTrigger>
            </div>
            <DialogContent className="flex flex-col items-center max-w-sm">
              <BadgeQrDisplay
                payload={data.qr_payload}
                displayName={data.employee_display_name}
                username={data.badge_username}
                size={280}
              />
            </DialogContent>
          </Dialog>
        </Card>
      )}

      <Card className="p-4">
        <BadgeuseDayTimeline data={data} />
      </Card>

      {showToggle && (
        <Card className="p-4 flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            Badgeage à distance (télétravail)
          </p>
          <Button
            size="lg"
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
          >
            {mutation.isPending
              ? "Enregistrement…"
              : data.next_action === "ENTREE"
                ? "Badger mon arrivée"
                : "Badger mon départ"}
          </Button>
        </Card>
      )}

      {isToday && data.allow_self_toggle === false && (
        <p className="text-center text-sm text-muted-foreground">
          Le badgeage se fait uniquement via scan QR à l&apos;accueil.
        </p>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}
    </div>
  );
}
