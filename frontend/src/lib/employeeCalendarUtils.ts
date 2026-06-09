import type { PlannedEventData } from '@/api/calendar';

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
