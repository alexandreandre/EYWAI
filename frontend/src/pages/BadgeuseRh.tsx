import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  DaySummary,
  DayDetail,
} from "@/api/badgeuse";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";

function secondsToHoursLabel(totalSeconds: number): string {
  if (!totalSeconds || totalSeconds <= 0) return "0h00";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${hours}h${minutes.toString().padStart(2, "0")}`;
}

export default function BadgeuseRhPage() {
  const { activeCompany } = useCompany();
  const queryClient = useQueryClient();
  const [from, setFrom] = useState<string>(new Date().toISOString().slice(0, 10));
  const [to, setTo] = useState<string>(new Date().toISOString().slice(0, 10));
  const [withAnomaliesOnly, setWithAnomaliesOnly] = useState(false);
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<string | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [newEventType, setNewEventType] = useState<"ENTREE" | "SORTIE">("ENTREE");
  const [newEventTime, setNewEventTime] = useState<string>("09:00");
  const [editEventId, setEditEventId] = useState<string | null>(null);
  const [editEventTime, setEditEventTime] = useState<string>("");
  const [editEventType, setEditEventType] = useState<"ENTREE" | "SORTIE">("ENTREE");
  const [validatingWeek, setValidatingWeek] = useState(false);

  const companyId = activeCompany?.company_id;

  const { data, isLoading, isError } = useQuery({
    queryKey: ["badgeuse", "summary", companyId, from, to, withAnomaliesOnly],
    queryFn: () =>
      getCompanyBadgeuseSummary(companyId as string, from, to, withAnomaliesOnly),
    enabled: !!companyId,
  });

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

  return (
    <div className="space-y-4">
      <Card className="p-4 space-y-3">
        <h1 className="text-xl font-semibold">Badgeuse - Synthèse RH</h1>
        <div className="flex flex-wrap gap-4 items-end">
          <div className="flex flex-col">
            <label className="text-xs text-muted-foreground mb-1">Du</label>
            <Input
              type="date"
              value={from}
              onChange={(e) => setFrom(e.target.value)}
            />
          </div>
          <div className="flex flex-col">
            <label className="text-xs text-muted-foreground mb-1">Au</label>
            <Input
              type="date"
              value={to}
              onChange={(e) => setTo(e.target.value)}
            />
          </div>
          <label className="inline-flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={withAnomaliesOnly}
              onChange={(e) => setWithAnomaliesOnly(e.target.checked)}
            />
            Afficher uniquement les employés avec anomalies
          </label>
          <Button
            asChild
            variant="outline"
            className="ml-auto"
            disabled={!data || data.length === 0}
          >
            <a href={exportBadgeuseCsvUrl(companyId, from, to)}>
              Export CSV
            </a>
          </Button>
        </div>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-[2fr_1.5fr] gap-4">
        <Card className="min-w-0 p-0">
          <div className="w-full overflow-x-auto">
            <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                <th className="px-4 py-2 text-left">Employé</th>
                <th className="px-4 py-2 text-left">Total heures</th>
                <th className="px-4 py-2 text-left">Jours en anomalie</th>
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
                  <td colSpan={3} className="px-4 py-3 text-red-600">
                    Erreur lors du chargement de la synthèse.
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
                    className={`border-t cursor-pointer hover:bg-muted/50 ${
                      selectedEmployeeId === row.employee_id ? "bg-muted/70" : ""
                    }`}
                    onClick={() => {
                      setSelectedEmployeeId(row.employee_id);
                      setSelectedDay(null);
                    }}
                  >
                    <td className="px-4 py-2">
                      {row.employee_name ?? row.employee_id}
                    </td>
                    <td className="px-4 py-2">
                      {secondsToHoursLabel(row.total_seconds)}
                    </td>
                    <td className="px-4 py-2">
                      {row.days_with_anomalies > 0
                        ? `${row.days_with_anomalies} jour(s)`
                        : "Aucune"}
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
                                  ({e.source === "EMPLOYE" ? "Employé" : "RH"})
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
    </div>
  );
}

