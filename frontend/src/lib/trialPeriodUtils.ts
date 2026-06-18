import { addDays, addMonths, format, parseISO } from "date-fns";
import { fr } from "date-fns/locale";

export type TrialPeriodUnit = "jours" | "semaines" | "mois";

export function computeTrialPeriodEndDate(
  hireDateIso: string,
  duree: number,
  unite: TrialPeriodUnit,
): Date | null {
  if (!hireDateIso || duree <= 0) return null;
  const hire = parseISO(hireDateIso.slice(0, 10));
  if (Number.isNaN(hire.getTime())) return null;

  if (unite === "jours") return addDays(hire, duree);
  if (unite === "semaines") return addDays(hire, duree * 7);
  return addMonths(hire, duree);
}

export function formatTrialPeriodEndPreview(
  hireDateIso: string,
  duree: number,
  unite: TrialPeriodUnit,
): string | null {
  const end = computeTrialPeriodEndDate(hireDateIso, duree, unite);
  if (!end) return null;

  const endLabel = format(end, "d MMMM yyyy", { locale: fr });
  const unitLabel =
    unite === "jours"
      ? duree === 1
        ? "jour"
        : "jours"
      : unite === "semaines"
        ? duree === 1
          ? "semaine"
          : "semaines"
        : duree === 1
          ? "mois"
          : "mois";

  return `Fin prévue le ${endLabel} (${duree} ${unitLabel} à compter de la date d'entrée)`;
}

export function formatHireDateLong(hireDateIso: string): string {
  return format(parseISO(hireDateIso.slice(0, 10)), "d MMMM yyyy", { locale: fr });
}
