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

const ABSENCE_HOUR_TYPES = new Set(['arret_maladie', 'absence']);

export interface EmployeeCalendarSummary {
  heuresFaites: number;
  heuresSupplementaires: number;
  congesPris: number;
  heuresAbsence: number;
  isForfaitJour: boolean;
}

/** Synthèse mensuelle simplifiée pour la page calendrier employé. */
export function computeEmployeeCalendarSummary(
  planned: PlannedEventData[],
  actual: ActualHoursData[],
  isForfaitJour: boolean
): EmployeeCalendarSummary {
  const base = computeMonthStats(planned, actual, isForfaitJour);
  const actualByDay = new Map(actual.map((a) => [a.jour, a]));

  let heuresSupplementaires = 0;
  let heuresAbsence = 0;

  for (const p of planned) {
    if (ABSENCE_HOUR_TYPES.has(p.type)) {
      heuresAbsence += p.heures_prevues ?? (isForfaitJour ? 1 : 0);
    }
    if (p.type === 'travail' && !isForfaitJour) {
      const faites = actualByDay.get(p.jour)?.heures_faites ?? 0;
      const prevues = p.heures_prevues ?? 0;
      if (faites > prevues) {
        heuresSupplementaires += faites - prevues;
      }
    }
  }

  return {
    heuresFaites: isForfaitJour ? base.joursTravaillesForfait : base.heuresFaites,
    heuresSupplementaires,
    congesPris: base.conges,
    heuresAbsence,
    isForfaitJour,
  };
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

function hasHourValue(value: number | null | undefined): boolean {
  return value !== null && value !== undefined;
}

/** Jour prêt pour la paie : type travail exige prévu + réel ; les autres types sont complets en l'état. */
export function isDayReadyForPayroll(
  plannedDay: PlannedEventData | undefined,
  actualDay: ActualHoursData | undefined,
  isForfaitJour = false
): boolean {
  if (!plannedDay) return false;
  if (plannedDay.type === 'travail') {
    if (!hasHourValue(plannedDay.heures_prevues)) return false;
    if (!hasHourValue(actualDay?.heures_faites)) return false;
    const prev = plannedDay.heures_prevues as number;
    const fait = actualDay!.heures_faites as number;
    // Horaire : 0 h sur un jour prévu = pas encore saisi (distinct du forfait 0/1).
    if (!isForfaitJour && prev > 0 && fait <= 0) return false;
    return true;
  }
  return true;
}

export function computeEmployeeRowStatus(
  planned: PlannedEventData[],
  actual: ActualHoursData[],
  year: number,
  month: number,
  isForfaitJour: boolean
): EmployeeRowStatus {
  const completion = computeMonthCompletionStatus(
    planned,
    actual,
    year,
    month,
    isForfaitJour
  );
  if (completion === 'a_saisir') return 'a_saisir';
  const stats = computeMonthStats(planned, actual, isForfaitJour);
  if (isForfaitJour) {
    return stats.ecartJours !== 0 ? 'saisi_avec_ecart' : 'saisi';
  }
  return isSignificantEcart(stats.heuresPrevues, stats.heuresFaites)
    ? 'saisi_avec_ecart'
    : 'saisi';
}

/** Mois prêt pour la paie : chaque jour travail du mois a prévu et réel renseignés. */
export function computeMonthCompletionStatus(
  planned: PlannedEventData[],
  actual: ActualHoursData[],
  year: number,
  month: number,
  isForfaitJour = false
): MonthCompletionStatus {
  const daysInMonth = new Date(year, month, 0).getDate();
  const plannedByDay = new Map(planned.map((p) => [p.jour, p]));
  const actualByDay = new Map(actual.map((a) => [a.jour, a]));

  for (let day = 1; day <= daysInMonth; day++) {
    const plannedDay = plannedByDay.get(day);
    const actualDay = actualByDay.get(day);
    if (!isDayReadyForPayroll(plannedDay, actualDay, isForfaitJour)) {
      return 'a_saisir';
    }
  }
  return 'saisi';
}
