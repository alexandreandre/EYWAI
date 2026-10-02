import type { ActualHoursData as ApiActualHoursData, PlannedEventData } from '@/api/calendar';

/** Les calculs ne lisent que le jour et les heures faites du réel. */
type ActualHoursData = Pick<ApiActualHoursData, 'jour' | 'heures_faites'>;

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
    if ((p.type === 'travail' || p.type === 'work') && !isForfaitJour) {
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

/** Forme minimale d'une demande d'absence (module Absences). */
export interface AbsenceLike {
  status?: string | null;
  type?: string | null;
  selected_days?: string[] | null;
}

/** Jours CALENDAIRES d'arrêt du mois (samedis/dimanches compris), depuis les
 * absences validées. Les cases du calendrier ne portent que les jours ouvrés
 * (design « bornes calendaires » : les week-ends ne sont jamais retypés) —
 * le décompte prévoyance/IJSS se fait donc ici, sur selected_days. */
export function joursArretCalendairesDuMois(
  absences: AbsenceLike[],
  year: number,
  month: number
): number {
  const prefix = `${year}-${String(month).padStart(2, '0')}-`;
  const jours = new Set<string>();
  for (const a of absences) {
    if (a.status !== 'validated') continue;
    if (!String(a.type ?? '').startsWith('arret')) continue;
    for (const iso of a.selected_days ?? []) {
      if (iso.startsWith(prefix)) jours.add(iso);
    }
  }
  return jours.size;
}

/** Total annuel des jours calendaires d'arrêt (même définition que le mois). */
export function joursArretCalendairesDeLAnnee(
  absences: AbsenceLike[],
  year: number
): number {
  const prefix = `${year}-`;
  const jours = new Set<string>();
  for (const a of absences) {
    if (a.status !== 'validated') continue;
    if (!String(a.type ?? '').startsWith('arret')) continue;
    for (const iso of a.selected_days ?? []) {
      if (iso.startsWith(prefix)) jours.add(iso);
    }
  }
  return jours.size;
}

/** Jours JTC validés de l'année — le type jtc n'écrit jamais le calendrier,
 * seules les demandes d'absence peuvent alimenter ce compteur. */
export function joursJtcDeLAnnee(
  absences: AbsenceLike[],
  year: number
): number {
  const prefix = `${year}-`;
  const jours = new Set<string>();
  for (const a of absences) {
    if (a.status !== 'validated' || a.type !== 'jtc') continue;
    for (const iso of a.selected_days ?? []) {
      if (iso.startsWith(prefix)) jours.add(iso);
    }
  }
  return jours.size;
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
    if (p.type === 'conge' || p.type === 'conges_payes' || p.type === 'rtt')
      // Une demi-journée de CP (quotite_absence = 0.5) compte 0,5 jour.
      conges += p.quotite_absence != null && p.quotite_absence > 0 && p.quotite_absence < 1
        ? p.quotite_absence
        : 1;
    else if (p.type === 'arret_maladie') arrets += 1;
    else if (p.type === 'ferie') feriels += 1;
    else if (p.type === 'travail' || p.type === 'work') {
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
    joursPrevus = planned.filter(
      (p) => (p.type === 'travail' || p.type === 'work') && p.heures_prevues === 1
    ).length;
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

/**
 * Une heure au moins pointée au réel. Même critère que le moteur de paie
 * (`planning_repli.mois_sans_pointage`) : sans aucune heure > 0, il ne lit pas
 * le réel et paie le prévu. Un jour vide ou à 0 h ne fait pas un salarié qui pointe.
 */
export function aDesHeuresPointees(actual: readonly ActualHoursData[]): boolean {
  return actual.some((a) => typeof a.heures_faites === 'number' && a.heures_faites > 0);
}

/**
 * Le salarié pointe-t-il sur la période de paie du mois ? Comme le juge du
 * serveur (`periode_a_saisir`), on regarde le mois et le précédent, que la
 * fenêtre des variables chevauche. Mois précédent illisible (`null`) : on
 * garde la règle stricte plutôt que de taire un mois oublié.
 */
export function pointeSurLaPeriode(
  actualDuMois: readonly ActualHoursData[],
  actualDuMoisPrecedent: readonly ActualHoursData[] | null
): boolean {
  if (actualDuMoisPrecedent === null) return true;
  return aDesHeuresPointees(actualDuMois) || aDesHeuresPointees(actualDuMoisPrecedent);
}

export function moisPrecedent(year: number, month: number): { year: number; month: number } {
  return month === 1 ? { year: year - 1, month: 12 } : { year, month: month - 1 };
}

/**
 * Jour prêt pour la paie : type travail exige prévu + réel ; les autres types sont complets en l'état.
 * `pointe` à faux (salarié qui ne pointe pas) : un jour sans réel n'attend rien, le prévu
 * fait foi ; un 0 h saisi un jour travaillé reste à saisir. Par défaut, règle stricte.
 */
export function isDayReadyForPayroll(
  plannedDay: PlannedEventData | undefined,
  actualDay: ActualHoursData | undefined,
  isForfaitJour = false,
  pointe = true
): boolean {
  if (!plannedDay) return false;
  if (plannedDay.type === 'travail' || plannedDay.type === 'work') {
    if (!hasHourValue(plannedDay.heures_prevues)) return false;
    if (!hasHourValue(actualDay?.heures_faites)) return !pointe;
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
  isForfaitJour: boolean,
  pointe = true
): EmployeeRowStatus {
  const completion = computeMonthCompletionStatus(
    planned,
    actual,
    year,
    month,
    isForfaitJour,
    pointe
  );
  if (completion === 'a_saisir') return 'a_saisir';
  // Sans aucune heure pointée, le prévu fait foi : pas d'écart à signaler.
  // Sauf un 0 saisi un jour travaillé (forfait à 0 jour) : le moteur paierait
  // le prévu, l'écart est le seul signal.
  const joursTravailles = new Set(
    planned.filter((p) => p.type === 'travail' || p.type === 'work').map((p) => p.jour)
  );
  const zeroUnJourTravaille = actual.some(
    (a) => joursTravailles.has(a.jour) && a.heures_faites === 0
  );
  if (!aDesHeuresPointees(actual) && !zeroUnJourTravaille) return 'saisi';
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
  isForfaitJour = false,
  pointe = true
): MonthCompletionStatus {
  const daysInMonth = new Date(year, month, 0).getDate();
  const plannedByDay = new Map(planned.map((p) => [p.jour, p]));
  const actualByDay = new Map(actual.map((a) => [a.jour, a]));

  for (let day = 1; day <= daysInMonth; day++) {
    const plannedDay = plannedByDay.get(day);
    const actualDay = actualByDay.get(day);
    if (!isDayReadyForPayroll(plannedDay, actualDay, isForfaitJour, pointe)) {
      return 'a_saisir';
    }
  }
  return 'saisi';
}
