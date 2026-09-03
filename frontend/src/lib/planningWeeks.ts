/**
 * Semaines du calendrier planning : chunks lundi–dimanche,
 * identiques aux onglets « Sem. 1 (3–9) » de la vue équipe.
 */

export function computePlanningWeeks(year: number, month: number): number[][] {
  const daysInMonth = new Date(year, month, 0).getDate();
  const firstDow = (new Date(year, month - 1, 1).getDay() + 6) % 7;
  const weeks: number[][] = [];
  let current: number[] = Array(firstDow).fill(0);

  for (let day = 1; day <= daysInMonth; day += 1) {
    current.push(day);
    if (current.length === 7) {
      weeks.push(current);
      current = [];
    }
  }
  if (current.length > 0) {
    while (current.length < 7) current.push(0);
    weeks.push(current);
  }
  return weeks;
}

export function planningWeekDays(week: number[]): number[] {
  return week.filter((day) => day > 0);
}

export function planningWeekLabel(week: number[]): string {
  const days = planningWeekDays(week);
  if (days.length === 0) return '';
  if (days.length === 1) return String(days[0]);
  return `${days[0]}–${days[days.length - 1]}`;
}

export function defaultPlanningWeekIndex(
  year: number,
  month: number,
  today: Date = new Date(),
): number {
  if (today.getFullYear() !== year || today.getMonth() + 1 !== month) {
    return 0;
  }
  const day = today.getDate();
  const weeks = computePlanningWeeks(year, month);
  const index = weeks.findIndex((week) => week.includes(day));
  return index >= 0 ? index : 0;
}

/** Numéro de semaine ISO (S27, S28…) d'un chunk du mois — celui du premier
 * jour renseigné (les onglets « Sem. 1, 2, 3 » ne parlaient à personne en
 * paie, cf. retour Gaëlle 03/09). */
export function planningWeekIsoNumber(
  year: number,
  month: number,
  week: number[],
): number | null {
  const days = planningWeekDays(week);
  if (days.length === 0) return null;
  const d = new Date(year, month - 1, days[0]);
  // ISO 8601 : la semaine est celle de son jeudi.
  const jeudi = new Date(d);
  jeudi.setDate(d.getDate() - ((d.getDay() + 6) % 7) + 3);
  const premierJeudiAn = new Date(jeudi.getFullYear(), 0, 4);
  const diffJours = Math.round(
    (jeudi.getTime() - premierJeudiAn.getTime()) / 86_400_000,
  );
  return 1 + Math.floor((diffJours + ((premierJeudiAn.getDay() + 6) % 7)) / 7);
}
