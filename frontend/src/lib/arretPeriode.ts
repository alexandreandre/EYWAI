// Période calendaire d'un arrêt de travail (spec 2026-09-01) : l'expansion en
// jours est faite par le serveur ; le front ne fait que compter et afficher.
import { differenceInCalendarDays, format } from "date-fns";

/** Nombre de jours calendaires d'une période, bornes incluses. */
export function nbJoursCalendaires(from: Date, to: Date): number {
  return differenceInCalendarDays(to, from) + 1;
}

/** Libellé du sélecteur de période d'arrêt. */
export function formatPeriodeArret(from: Date, to?: Date): string {
  const debut = format(from, "dd/MM/yyyy");
  if (!to) return `Du ${debut} au …`;
  const fin = format(to, "dd/MM/yyyy");
  const n = nbJoursCalendaires(from, to);
  const s = n > 1 ? "s" : "";
  return `Du ${debut} au ${fin} (${n} jour${s} calendaire${s})`;
}
