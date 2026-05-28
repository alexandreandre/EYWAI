import type { ActualHoursData, PlannedEventData } from '@/api/calendar';
import { computeMonthStats, isSignificantEcart } from '@/lib/calendarStats';

export function dayHasSignificantEcart(
  heuresPrevues: number | null | undefined,
  heuresFaites: number | null | undefined,
  isForfaitJour: boolean
): boolean {
  if (isForfaitJour) {
    const p = heuresPrevues === 1 ? 1 : 0;
    const a = heuresFaites === 1 ? 1 : 0;
    if (heuresPrevues == null && heuresFaites == null) return false;
    return p !== a;
  }
  const p = heuresPrevues ?? 0;
  const a = heuresFaites ?? 0;
  if (heuresPrevues == null && heuresFaites == null) return false;
  return isSignificantEcart(p, a);
}

/** Tous les jours ouvrés du mois sans heures prévues renseignées. */
export function isMonthUnfilledByRh(
  planned: PlannedEventData[],
  year: number,
  month: number
): boolean {
  const daysInMonth = new Date(year, month, 0).getDate();
  let weekdayCount = 0;
  let unfilledCount = 0;

  for (let day = 1; day <= daysInMonth; day++) {
    const date = new Date(year, month - 1, day);
    const dow = date.getDay();
    if (dow === 0 || dow === 6) continue;
    weekdayCount += 1;
    const row = planned.find((p) => p.jour === day);
    if (!row || row.heures_prevues === null || row.heures_prevues === undefined) {
      unfilledCount += 1;
    }
  }

  return weekdayCount > 0 && unfilledCount === weekdayCount;
}

export function monthHasSignificantEcart(
  planned: PlannedEventData[],
  actual: ActualHoursData[],
  isForfaitJour: boolean
): boolean {
  const stats = computeMonthStats(planned, actual, isForfaitJour);
  if (isForfaitJour) return stats.ecartJours !== 0;
  return isSignificantEcart(stats.heuresPrevues, stats.heuresFaites);
}
