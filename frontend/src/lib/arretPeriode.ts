// Période calendaire d'un arrêt de travail (spec 2026-09-01) : l'expansion en
// jours est faite par le serveur ; le front ne fait que compter et afficher.
import { differenceInCalendarDays, format } from "date-fns";
import { fr } from "date-fns/locale";

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

/**
 * La période d'un arrêt en toutes lettres, pour le double contrôle avant
 * d'enregistrer (retour d'Elsa) : « du lundi 05/10/2026 au vendredi 16/10/2026
 * (12 jours calendaires) ».
 */
export function periodeArretEnToutesLettres(from: Date, to: Date): string {
  const jour = (d: Date) => format(d, "EEEE dd/MM/yyyy", { locale: fr });
  const n = nbJoursCalendaires(from, to);
  const s = n > 1 ? "s" : "";
  const compte = `(${n} jour${s} calendaire${s})`;
  if (n <= 1) return `le ${jour(from)} ${compte}`;
  return `du ${jour(from)} au ${jour(to)} ${compte}`;
}
