import type { QueryClient } from "@tanstack/react-query";

/** Invalide les KPI / badges partagés entre Pilotage et la page Formation. */
export function invalidateFormationHub(qc: QueryClient) {
  void qc.invalidateQueries({ queryKey: ["formation-page"] });
  void qc.invalidateQueries({ queryKey: ["formation-pilotage"] });
  void qc.invalidateQueries({ queryKey: ["formation-evaluations-summary"] });
}
