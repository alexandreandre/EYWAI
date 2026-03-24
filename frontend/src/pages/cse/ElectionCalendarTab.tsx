// frontend/src/pages/cse/ElectionCalendarTab.tsx
// Onglet Calendrier électoral

import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getElectionCycles, getElectionAlerts, type ElectionCycle } from "@/api/cse";
import { CalendarDays, AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";

export default function ElectionCalendarTab() {
  const { data: cycles = [], isLoading: loadingCycles } = useQuery({
    queryKey: ["cse", "election-cycles"],
    queryFn: () => getElectionCycles(),
  });

  const { data: alerts = [], isLoading: loadingAlerts } = useQuery({
    queryKey: ["cse", "election-alerts"],
    queryFn: () => getElectionAlerts(),
  });

  if (loadingCycles || loadingAlerts) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="h-6 w-6 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Alertes */}
      {alerts.length > 0 && (
        <Card className="border-orange-200">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-orange-900">
              <AlertTriangle className="h-5 w-5" />
              Alertes électorales
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {alerts.map((alert) => (
                <div key={alert.cycle_id} className="flex items-center justify-between">
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

      {/* Cycles électoraux */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <CalendarDays className="h-5 w-5" />
            Cycles électoraux
          </CardTitle>
        </CardHeader>
        <CardContent>
          {cycles.length === 0 ? (
            <div className="text-center py-8 text-muted-foreground">
              Aucun cycle électoral trouvé
            </div>
          ) : (
            <div className="space-y-4">
              {cycles.map((cycle) => (
                <Card key={cycle.id} className="border-l-4 border-l-blue-500">
                  <CardContent className="pt-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <h3 className="font-semibold text-lg">{cycle.cycle_name}</h3>
                        <p className="text-sm text-muted-foreground mt-1">
                          Fin de mandat : {new Date(cycle.mandate_end_date).toLocaleDateString("fr-FR")}
                        </p>
                        {cycle.days_until_mandate_end !== null && (
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
                        {cycle.status === "completed" ? "Terminé" : "En cours"}
                      </Badge>
                    </div>
                    {cycle.timeline && cycle.timeline.length > 0 && (
                      <div className="mt-4 space-y-2">
                        <h4 className="text-sm font-medium">Timeline :</h4>
                        {cycle.timeline.map((step) => (
                          <div key={step.id} className="flex items-center gap-2 text-sm">
                            {step.status === "completed" ? (
                              <CheckCircle2 className="h-4 w-4 text-green-600" />
                            ) : (
                              <div className="h-4 w-4 rounded-full border-2 border-gray-300" />
                            )}
                            <span className={step.status === "completed" ? "line-through text-muted-foreground" : ""}>
                              {step.step_name}
                            </span>
                            <span className="text-muted-foreground ml-auto">
                              {new Date(step.due_date).toLocaleDateString("fr-FR")}
                            </span>
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
    </div>
  );
}
