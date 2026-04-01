import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { getMyBadgeuseStatusToday, toggleMyBadge } from "@/api/badgeuse";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

function formatSecondsToHoursMinutes(totalSeconds: number | undefined): string {
  if (!totalSeconds || totalSeconds <= 0) return "0h00";
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  return `${hours}h${minutes.toString().padStart(2, "0")}`;
}

export default function EmployeeBadgeusePage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [selectedDate, setSelectedDate] = useState<string>(
    new Date().toISOString().slice(0, 10)
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: ["badgeuse", "status-today", selectedDate],
    queryFn: () => getMyBadgeuseStatusToday(selectedDate),
  });

  const mutation = useMutation({
    mutationFn: toggleMyBadge,
    onSuccess: (newStatus) => {
      queryClient.setQueryData(["badgeuse", "status-today"], newStatus);
      setError(null);
    },
    onError: (err: any) => {
      const message =
        err?.response?.data?.detail ||
        err?.message ||
        "Une erreur est survenue lors du badgeage.";
      setError(message);
    },
  });

  if (isLoading) {
    return <div>Chargement de la badgeuse...</div>;
  }

  if (isError || !data) {
    return <div>Impossible de charger la badgeuse.</div>;
  }

  if (!data.is_eligible_for_badgeuse) {
    return (
      <Card className="p-6 space-y-2">
        <h1 className="text-xl font-semibold">Badgeuse</h1>
        <p className="text-sm text-muted-foreground">
          {data.reason || "La badgeuse n'est pas applicable à votre profil."}
        </p>
      </Card>
    );
  }

  const totalLabel = formatSecondsToHoursMinutes(data.total_seconds);

  const nextActionLabel =
    data.next_action === "ENTREE" ? "Badger mon arrivée" : "Badger mon départ";

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      <Card className="p-6 space-y-4">
        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between gap-4">
            <div>
              <h1 className="text-xl font-semibold mb-1">Ma badgeuse</h1>
              <p className="text-sm text-muted-foreground">
                {data.status_label}
              </p>
            </div>
            <div className="flex flex-col items-end gap-1">
              <span className="text-xs text-muted-foreground">Date consultée</span>
              <input
                type="date"
                value={selectedDate}
                onChange={(e) => setSelectedDate(e.target.value)}
                className="border rounded px-2 py-1 text-xs"
              />
            </div>
          </div>
          {data.date && (
            <p className="text-xs text-muted-foreground">
              Jour affiché : {data.date}
            </p>
          )}
        </div>

        <div className="flex items-center justify-between">
          <div>
            <div className="text-sm font-medium">Temps de présence estimé aujourd'hui</div>
            <div className="text-2xl font-bold">{totalLabel}</div>
          </div>
          <Button
            size="lg"
            onClick={() => mutation.mutate()}
            disabled={mutation.isLoading || selectedDate !== new Date().toISOString().slice(0, 10)}
            title={
              selectedDate !== new Date().toISOString().slice(0, 10)
                ? "Le badgeage n'est possible que pour la journée en cours."
                : undefined
            }
          >
            {mutation.isLoading ? "Enregistrement..." : nextActionLabel}
          </Button>
        </div>

        {error && (
          <p className="text-sm text-red-600">
            {error}
          </p>
        )}
      </Card>

      <Card className="p-4">
        <h2 className="text-lg font-semibold mb-2">Historique de la journée</h2>
        {data.events && data.events.length > 0 ? (
          <ul className="space-y-1 text-sm">
            {data.events.map((e) => (
              <li key={e.id ?? e.timestamp} className="flex justify-between">
                <span>
                  {e.event_type === "ENTREE" ? "Entrée" : "Sortie"}{" "}
                  ({new Date(e.timestamp).toLocaleTimeString("fr-FR", {
                    hour: "2-digit",
                    minute: "2-digit",
                  })})
                </span>
                <span className="text-xs text-muted-foreground">
                  {e.source === "EMPLOYE" ? "Employé" : "RH"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-muted-foreground">
            Aucun événement enregistré pour aujourd'hui.
          </p>
        )}
      </Card>
    </div>
  );
}

