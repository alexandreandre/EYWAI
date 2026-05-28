import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getEmployeeDayDetail,
  addEmployeeDayEvent,
  updateBadgeuseEvent,
  deleteBadgeuseEvent,
  validateEmployeeDay,
  type DayDetail,
} from "@/api/badgeuse";
import {
  formatSecondsToHoursMinutes,
  sourceLabel,
} from "@/lib/badgeuseFormat";
import { formatBadgeuseDate, dayStatusLabel } from "@/lib/badgeuseApiUtils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { toast } from "sonner";

type Props = {
  employeeId: string;
  companyId: string;
  day: string | null;
  periodFrom: string;
  periodTo: string;
  title?: string;
  emptyMessage?: string;
};

function invalidateDayQueries(
  queryClient: ReturnType<typeof useQueryClient>,
  companyId: string,
  employeeId: string,
  day: string | null,
  periodFrom: string,
  periodTo: string
) {
  if (day) {
    void queryClient.invalidateQueries({
      queryKey: ["badgeuse", "employee-day-detail", companyId, employeeId, day],
    });
  }
  void queryClient.invalidateQueries({
    queryKey: ["badgeuse", "employee-days", companyId, employeeId, periodFrom, periodTo],
  });
}

export function EmployeeBadgeuseDayDetail({
  employeeId,
  companyId,
  day,
  periodFrom,
  periodTo,
  title = "Détail de la journée",
  emptyMessage = "Sélectionnez un jour pour voir et corriger les événements de pointage.",
}: Props) {
  const queryClient = useQueryClient();
  const [newEventType, setNewEventType] = useState<"ENTREE" | "SORTIE">("ENTREE");
  const [newEventTime, setNewEventTime] = useState("09:00");
  const [editEventId, setEditEventId] = useState<string | null>(null);
  const [editEventTime, setEditEventTime] = useState("");
  const [editEventType, setEditEventType] = useState<"ENTREE" | "SORTIE">("ENTREE");

  const enabled = Boolean(companyId && employeeId && day);

  const { data: dayDetail, isLoading, isFetching } = useQuery<DayDetail | undefined>({
    queryKey: ["badgeuse", "employee-day-detail", companyId, employeeId, day],
    queryFn: () => getEmployeeDayDetail(employeeId, companyId, day as string),
    enabled,
  });

  const onMutationSuccess = (message: string) => {
    toast.success(message);
    invalidateDayQueries(queryClient, companyId, employeeId, day, periodFrom, periodTo);
  };

  const onMutationError = (err: unknown, fallback: string) => {
    const message =
      (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
      fallback;
    toast.error(String(message));
  };

  const addEventMutation = useMutation({
    mutationFn: () =>
      addEmployeeDayEvent(employeeId, companyId, day as string, {
        event_type: newEventType,
        time: newEventTime,
      }),
    onSuccess: () => onMutationSuccess("Événement ajouté."),
    onError: (e) => onMutationError(e, "Impossible d'ajouter l'événement."),
  });

  const updateEventMutation = useMutation({
    mutationFn: () =>
      updateBadgeuseEvent(editEventId as string, companyId, {
        time: editEventTime,
        event_type: editEventType,
        date: day as string,
      }),
    onSuccess: () => {
      setEditEventId(null);
      onMutationSuccess("Événement mis à jour.");
    },
    onError: (e) => onMutationError(e, "Impossible de modifier l'événement."),
  });

  const deleteEventMutation = useMutation({
    mutationFn: (eventId: string) => deleteBadgeuseEvent(eventId, companyId),
    onSuccess: () => onMutationSuccess("Événement supprimé."),
    onError: (e) => onMutationError(e, "Impossible de supprimer l'événement."),
  });

  const validateDayMutation = useMutation({
    mutationFn: () => validateEmployeeDay(employeeId, companyId, day as string),
    onSuccess: () => onMutationSuccess("Journée validée."),
    onError: (e) => onMutationError(e, "Impossible de valider la journée."),
  });

  if (!day) {
    return (
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">{title}</h4>
        <p className="text-sm text-muted-foreground">{emptyMessage}</p>
      </div>
    );
  }

  if (isLoading || (isFetching && !dayDetail)) {
    return (
      <div className="space-y-3">
        <h4 className="text-sm font-semibold">{title}</h4>
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-20 w-full" />
        <Skeleton className="h-10 w-full" />
      </div>
    );
  }

  if (!dayDetail) {
    return (
      <div className="space-y-2">
        <h4 className="text-sm font-semibold">{title}</h4>
        <p className="text-sm text-muted-foreground">Impossible de charger cette journée.</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h4 className="text-sm font-semibold">{title}</h4>
      <div className="text-sm space-y-1">
        <div className="font-medium">
          {formatBadgeuseDate(dayDetail.date)} — {dayStatusLabel(dayDetail.status)}
        </div>
        {dayDetail.validated && (
          <div className="text-xs inline-flex items-center rounded-full bg-emerald-50 px-2 py-0.5 text-emerald-700 border border-emerald-200">
            Journée validée par un RH
          </div>
        )}
        <div className="text-muted-foreground">
          Temps de présence : {formatSecondsToHoursMinutes(dayDetail.total_seconds)}
        </div>
      </div>

      {dayDetail.anomalies.length > 0 && (
        <div className="rounded-md bg-amber-50 border border-amber-200 p-2 text-xs text-amber-900 space-y-1">
          <div className="font-semibold">Anomalies détectées</div>
          <ul className="list-disc list-inside space-y-0.5">
            {dayDetail.anomalies.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="space-y-2">
        <span className="text-sm font-medium">Événements</span>
        {dayDetail.events.length === 0 ? (
          <p className="text-sm text-muted-foreground">Aucun événement pour cette journée.</p>
        ) : (
          <ul className="space-y-2 text-sm">
            {dayDetail.events.map((e) => {
              const time = new Date(e.timestamp).toLocaleTimeString("fr-FR", {
                hour: "2-digit",
                minute: "2-digit",
              });
              const isEditing = editEventId === (e.id ?? "");
              return (
                <li
                  key={e.id ?? e.timestamp}
                  className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between"
                >
                  {!isEditing ? (
                    <>
                      <span>
                        {e.event_type === "ENTREE" ? "Entrée" : "Sortie"} à {time}{" "}
                        ({sourceLabel(e.source)})
                      </span>
                      <div className="flex gap-1 shrink-0">
                        <Button
                          size="xs"
                          variant="outline"
                          type="button"
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
                            type="button"
                            className="text-red-600"
                            onClick={() => deleteEventMutation.mutate(e.id as string)}
                            disabled={deleteEventMutation.isPending}
                          >
                            Supprimer
                          </Button>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="w-full flex flex-wrap items-center gap-2">
                      <Select
                        value={editEventType}
                        onValueChange={(v) => setEditEventType(v as "ENTREE" | "SORTIE")}
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
                          type="button"
                          onClick={() => updateEventMutation.mutate()}
                          disabled={updateEventMutation.isPending}
                        >
                          Enregistrer
                        </Button>
                        <Button
                          size="xs"
                          variant="ghost"
                          type="button"
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-sm font-medium">Ajouter un événement</span>
          <Button
            size="xs"
            variant="outline"
            type="button"
            onClick={() => validateDayMutation.mutate()}
            disabled={validateDayMutation.isPending}
          >
            {validateDayMutation.isPending ? "Validation…" : "Valider la journée"}
          </Button>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex flex-col">
            <Label className="text-xs mb-1">Type</Label>
            <Select
              value={newEventType}
              onValueChange={(v) => setNewEventType(v as "ENTREE" | "SORTIE")}
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
            className="sm:ml-auto"
            size="sm"
            type="button"
            onClick={() => addEventMutation.mutate()}
            disabled={addEventMutation.isPending}
          >
            {addEventMutation.isPending ? "Enregistrement…" : "Ajouter"}
          </Button>
        </div>
      </div>
    </div>
  );
}
