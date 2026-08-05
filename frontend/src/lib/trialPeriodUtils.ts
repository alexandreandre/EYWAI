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

  // La période expire la veille du quantième correspondant : deux mois à
  // compter du 1er mars s'achèvent le 30 avril, pas le 1er mai. Et le jour
  // d'embauche compte comme premier jour.
  if (unite === "jours") return addDays(hire, duree - 1);
  if (unite === "semaines") return addDays(hire, duree * 7 - 1);

  const target = addMonths(hire, duree);
  // addMonths a tronqué au dernier jour du mois (31 janvier + 1 mois donne le
  // 28 février) : c'est déjà le dernier jour de la période.
  if (target.getDate() !== hire.getDate()) return target;
  return addDays(target, -1);
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
