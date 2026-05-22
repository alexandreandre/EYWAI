import type { ActualHoursData, PlannedEventData } from '@/api/calendar';

export interface CalendarMonthStats {
  heuresPrevues: number;
  heuresFaites: number;
  ecart: number;
  joursTravailles: number;
  conges: number;
  arrets: number;
  feriels: number;
  joursPrevus: number;
  joursTravaillesForfait: number;
  ecartJours: number;
}

function sumHours(values: (number | null | undefined)[]): number {
  return values.reduce((acc, v) => acc + (typeof v === 'number' && !Number.isNaN(v) ? v : 0), 0);
}

export function computeMonthStats(
  planned: PlannedEventData[],
  actual: ActualHoursData[],
  isForfaitJour: boolean
): CalendarMonthStats {
  let conges = 0;
  let arrets = 0;
  let feriels = 0;
  let joursTravailles = 0;

  for (const p of planned) {
    if (p.type === 'conge') conges += 1;
    else if (p.type === 'arret_maladie') arrets += 1;
    else if (p.type === 'ferie') feriels += 1;
    else if (p.type === 'travail') {
      if (isForfaitJour ? p.heures_prevues === 1 : (p.heures_prevues ?? 0) > 0) {
        joursTravailles += 1;
      }
    }
  }

  const heuresPrevues = sumHours(planned.map((p) => p.heures_prevues));
  const heuresFaites = sumHours(actual.map((a) => a.heures_faites));

  let joursPrevus = 0;
  let joursTravaillesForfait = 0;
  if (isForfaitJour) {
    joursPrevus = planned.filter((p) => p.type === 'travail' && p.heures_prevues === 1).length;
    joursTravaillesForfait = actual.filter((a) => a.heures_faites === 1).length;
  }

  return {
    heuresPrevues,
    heuresFaites,
    ecart: heuresFaites - heuresPrevues,
    joursTravailles,
    conges,
    arrets,
    feriels,
    joursPrevus,
    joursTravaillesForfait,
    ecartJours: joursTravaillesForfait - joursPrevus,
  };
}

export type MonthCompletionStatus = 'a_saisir' | 'saisi';

export type EmployeeRowStatus = 'a_saisir' | 'saisi' | 'saisi_avec_ecart';

export const ECART_THRESHOLD_HOURS = 2;
export const ECART_THRESHOLD_RATIO = 0.1;

export function isSignificantEcart(heuresPrevues: number, heuresFaites: number): boolean {
  const ecart = Math.abs(heuresFaites - heuresPrevues);
  if (ecart <= ECART_THRESHOLD_HOURS) return false;
  if (heuresPrevues <= 0) return ecart > ECART_THRESHOLD_HOURS;
  return ecart / heuresPrevues > ECART_THRESHOLD_RATIO;
}

export function computeEmployeeRowStatus(
  planned: PlannedEventData[],
  actual: ActualHoursData[],
  year: number,
  month: number,
  isForfaitJour: boolean
): EmployeeRowStatus {
  const completion = computeMonthCompletionStatus(planned, year, month);
  if (completion === 'a_saisir') return 'a_saisir';
  const stats = computeMonthStats(planned, actual, isForfaitJour);
  if (isForfaitJour) {
    return stats.ecartJours !== 0 ? 'saisi_avec_ecart' : 'saisi';
  }
  return isSignificantEcart(stats.heuresPrevues, stats.heuresFaites)
    ? 'saisi_avec_ecart'
    : 'saisi';
}

/** Heuristique front : mois saisi si tous les jours ouvrés ont au moins une valeur prévue renseignée. */
export function computeMonthCompletionStatus(
  planned: PlannedEventData[],
  year: number,
  month: number
): MonthCompletionStatus {
  const daysInMonth = new Date(year, month, 0).getDate();
  for (let day = 1; day <= daysInMonth; day++) {
    const date = new Date(year, month - 1, day);
    const dow = date.getDay();
    if (dow === 0 || dow === 6) continue;
    const row = planned.find((p) => p.jour === day);
    if (!row || row.heures_prevues === null || row.heures_prevues === undefined) {
      return 'a_saisir';
    }
  }
  return 'saisi';
}
