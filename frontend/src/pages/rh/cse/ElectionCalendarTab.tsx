// frontend/src/pages/cse/ElectionCalendarTab.tsx

import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  getElectionCycles,
  getElectionAlerts,
  completeElectionTimelineStep,
  type ElectionCycle,
  type TimelineStepStatus,
} from "@/api/cse";
import { useToast } from "@/components/ui/use-toast";
import {
  ELECTION_CYCLE_STATUS_LABELS,
  TIMELINE_STEP_STATUS_LABELS,
} from "@/lib/cseLabels";
import { ElectionCycleModal } from "@/components/cse/ElectionCycleModal";
import { SharkFinLoader } from '@/components/SharkFinLoader';
import {
  CalendarDays,
  AlertTriangle,
  CheckCircle2,
  Loader2,
  Plus,
  Circle,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ElectionCalendarTabProps {
  /** Masquer le bloc alertes si déjà affiché en haut de page (accordéon). */
  showHeaderAlerts?: boolean;
}

function StepIcon({ status }: { status: TimelineStepStatus }) {
  if (status === "completed") {
    return <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0" />;
  }
  if (status === "overdue") {
    return <AlertTriangle className="h-4 w-4 text-red-600 shrink-0" />;
  }
  return <Circle className="h-4 w-4 text-muted-foreground shrink-0" />;
}

export default function ElectionCalendarTab({
  showHeaderAlerts = true,
}: ElectionCalendarTabProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [cycleModalOpen, setCycleModalOpen] = useState(false);
  const [completingStepId, setCompletingStepId] = useState<string | null>(null);

  const completeStepMutation = useMutation({
    mutationFn: ({ cycleId, stepId }: { cycleId: string; stepId: string }) =>
      completeElectionTimelineStep(cycleId, stepId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["cse", "election-cycles"] });
      queryClient.invalidateQueries({ queryKey: ["cse", "election-alerts"] });
      toast({ title: "Étape terminée", description: "L'obligation a été marquée comme réalisée." });
      setCompletingStepId(null);
    },
    onError: (error: unknown) => {
      const msg =
        error && typeof error === "object" && "message" in error
          ? String((error as { message?: string }).message)
          : "Impossible de valider cette étape";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
      setCompletingStepId(null);
    },
  });

  const { data: cycles = [], isLoading: loadingCycles } = useQuery({
    queryKey: ["cse", "election-cycles"],
    queryFn: () => getElectionCycles(),
  });

  const { data: alerts = [], isLoading: loadingAlerts } = useQuery({
    queryKey: ["cse", "election-alerts"],
    queryFn: () => getElectionAlerts(),
  });

  if (loadingCycles || loadingAlerts) {
    return <SharkFinLoader label="Chargement du calendrier électoral…" />;
  }

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button onClick={() => setCycleModalOpen(true)}>
          <Plus className="h-4 w-4 mr-2" />
          Nouveau cycle électoral
        </Button>
      </div>

      {showHeaderAlerts && alerts.length > 0 && (
        <Card className="border-orange-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base text-orange-900">
              <AlertTriangle className="h-5 w-5" />
              Alertes électorales
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div
                  key={alert.cycle_id}
                  className="flex flex-wrap items-center justify-between gap-2 text-sm"
                >
                  <div>
                    <span className="font-medium">{alert.cycle_name}</span>
                    <span className="text-muted-foreground ml-2">{alert.message}</span>
                  </div>
                  <Badge
                    variant={
                      alert.alert_level === "critical"
                        ? "destructive"
                        : alert.alert_level === "warning"
                          ? "default"
                          : "secondary"
                    }
                  >
                    J-{alert.days_remaining}
                  </Badge>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarDays className="h-5 w-5" />
            Cycles électoraux
          </CardTitle>
        </CardHeader>
        <CardContent>
          {cycles.length === 0 ? (
            <div className="text-center py-8 space-y-3">
              <p className="text-muted-foreground">Aucun cycle électoral enregistré.</p>
              <Button variant="outline" onClick={() => setCycleModalOpen(true)}>
                <Plus className="h-4 w-4 mr-2" />
                Créer un cycle
              </Button>
            </div>
          ) : (
            <div className="space-y-4">
              {cycles.map((cycle: ElectionCycle) => (
                <Card
                  key={cycle.id}
                  className={cn(
                    "border-l-4",
                    cycle.status === "completed"
                      ? "border-l-muted-foreground"
                      : "border-l-primary",
                  )}
                >
                  <CardContent className="pt-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h3 className="font-semibold text-lg">{cycle.cycle_name}</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          Fin de mandat :{" "}
                          {new Date(cycle.mandate_end_date).toLocaleDateString("fr-FR")}
                        </p>
                        {cycle.election_date && (
                          <p className="text-sm text-muted-foreground mt-0.5">
                            Élections :{" "}
                            {new Date(cycle.election_date).toLocaleDateString("fr-FR")}
                          </p>
                        )}
                        {cycle.days_until_mandate_end != null && (
                          <p className="text-sm mt-1">
                            {cycle.days_until_mandate_end > 0 ? (
                              <span className="text-orange-600">
                                {cycle.days_until_mandate_end} jours restants
                              </span>
                            ) : (
                              <span className="text-red-600">Mandat expiré</span>
                            )}
                          </p>
                        )}
                      </div>
                      <Badge variant={cycle.status === "completed" ? "default" : "secondary"}>
                        {ELECTION_CYCLE_STATUS_LABELS[cycle.status]}
                      </Badge>
                    </div>
                    {cycle.timeline && cycle.timeline.length > 0 && (
                      <div className="mt-4 space-y-2">
                        <h4 className="text-sm font-medium">Calendrier des obligations</h4>
                        {cycle.timeline.map((step) => (
                          <div
                            key={step.id}
                            className={cn(
                              "flex flex-wrap items-center gap-2 text-sm rounded-md px-2 py-1.5",
                              step.status === "overdue" && "bg-red-50 border border-red-100",
                            )}
                          >
                            <StepIcon status={step.status} />
                            <span
                              className={cn(
                                "flex-1 min-w-[120px]",
                                step.status === "completed" &&
                                  "line-through text-muted-foreground",
                                step.status === "overdue" && "font-medium text-red-800",
                              )}
                            >
                              {step.step_name}
                            </span>
                            <Badge variant="outline" className="text-xs">
                              {TIMELINE_STEP_STATUS_LABELS[step.status]}
                            </Badge>
                            <span className="text-muted-foreground tabular-nums">
                              {new Date(step.due_date).toLocaleDateString("fr-FR")}
                            </span>
                            {step.status !== "completed" && (
                              <Button
                                variant="outline"
                                size="sm"
                                className="h-7 text-xs ml-auto"
                                disabled={
                                  completeStepMutation.isPending &&
                                  completingStepId === step.id
                                }
                                onClick={() => {
                                  setCompletingStepId(step.id);
                                  completeStepMutation.mutate({
                                    cycleId: cycle.id,
                                    stepId: step.id,
                                  });
                                }}
                              >
                                {completeStepMutation.isPending &&
                                completingStepId === step.id ? (
                                  <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                  "Marquer terminé"
                                )}
                              </Button>
                            )}
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <ElectionCycleModal open={cycleModalOpen} onOpenChange={setCycleModalOpen} />
    </div>
  );
}
