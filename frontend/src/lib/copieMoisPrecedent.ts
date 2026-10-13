/**
 * « Copier mois précédent » : le rythme de la semaine, pas les numéros de jour.
 *
 * Copier le 5 septembre sur le 5 octobre faisait d'un lundi un samedi (rejeu
 * C1 du 12/10 : les heures badgées du 19 et du 20 octobre tombaient sur des
 * week-ends). Chaque jour du mois copié reçoit le type et les heures du jour
 * type du même jour de la semaine au mois précédent : le plus fréquent, hors
 * absences et fériés, qui ne sont pas un rythme.
 *
 * Sur le mois copié, les fériés et les absences déjà posés restent tels quels :
 * le planning les a posés (fériés de la société), la RH ou une demande validée
 * aussi.
 */

import type { PlannedEventData } from '@/api/calendar';
import { NON_COPYABLE_DAY_TYPES } from '@/lib/calendarTypes';
import { accord, pluriel } from '@/lib/pluriel';

/** Types d'absence : ni un rythme à recopier, ni un jour à recouvrir. */
const TYPES_ABSENCE: ReadonlySet<string> = new Set([
  ...NON_COPYABLE_DAY_TYPES,
  'arret_maladie',
  'absence_non_remuneree',
  'absence_justifiee',
]);

export type JourType = { type: string; heures_prevues: number | null };

export type CopieMoisPrecedent = {
  jours: PlannedEventData[];
  /** Jours fériés du mois copié laissés tels quels. */
  feriesGardes: number;
  /** Jours d'absence du mois copié laissés tels quels. */
  absencesGardees: number;
};

function jourDeLaSemaine(annee: number, mois: number, jour: number): number {
  return new Date(annee, mois - 1, jour).getDay();
}

function estAbsence(jour: PlannedEventData): boolean {
  return jour.origine === 'absence' || TYPES_ABSENCE.has(jour.type);
}

/**
 * Le jour type de chaque jour de la semaine (clé : 0 = dimanche … 6 = samedi,
 * comme `Date.getDay`) : le type et les heures les plus fréquents de ce jour
 * dans le mois source, absences et fériés exclus. À égalité, le premier du mois.
 */
export function joursTypesDeLaSemaine(
  source: readonly PlannedEventData[],
  annee: number,
  mois: number
): Map<number, JourType> {
  const comptes = new Map<number, Map<string, { jourType: JourType; n: number }>>();
  const dernierJour = new Date(annee, mois, 0).getDate();
  for (const jour of [...source].sort((a, b) => a.jour - b.jour)) {
    if (jour.jour < 1 || jour.jour > dernierJour) continue;
    if (estAbsence(jour) || jour.type === 'ferie') continue;
    const semaine = jourDeLaSemaine(annee, mois, jour.jour);
    const jourType = { type: jour.type, heures_prevues: jour.heures_prevues ?? null };
    const cle = `${jourType.type}|${jourType.heures_prevues}`;
    const parType = comptes.get(semaine) ?? new Map();
    const compte = parType.get(cle) ?? { jourType, n: 0 };
    compte.n += 1;
    parType.set(cle, compte);
    comptes.set(semaine, parType);
  }
  const types = new Map<number, JourType>();
  for (const [semaine, parType] of comptes) {
    let retenu: { jourType: JourType; n: number } | null = null;
    // L'ordre d'insertion suit le mois : à égalité, le premier reste.
    for (const compte of parType.values()) {
      if (!retenu || compte.n > retenu.n) retenu = compte;
    }
    if (retenu) types.set(semaine, retenu.jourType);
  }
  return types;
}

/** Le mois copié : chaque jour reçoit le jour type du même jour de la semaine. */
export function copierMoisPrecedent({
  source,
  anneeSource,
  moisSource,
  cible,
  annee,
  mois,
}: {
  source: readonly PlannedEventData[];
  anneeSource: number;
  moisSource: number;
  /** Le planning du mois copié tel qu'il est (fériés de la société compris). */
  cible: readonly PlannedEventData[];
  annee: number;
  mois: number;
}): CopieMoisPrecedent {
  const types = joursTypesDeLaSemaine(source, anneeSource, moisSource);
  const dernierJour = new Date(annee, mois, 0).getDate();
  const jours: PlannedEventData[] = [];
  let feriesGardes = 0;
  let absencesGardees = 0;
  for (let jour = 1; jour <= dernierJour; jour += 1) {
    const existant = cible.find((j) => j.jour === jour);
    if (existant && estAbsence(existant)) {
      absencesGardees += 1;
      jours.push(existant);
      continue;
    }
    if (existant?.type === 'ferie') {
      feriesGardes += 1;
      jours.push(existant);
      continue;
    }
    const semaine = jourDeLaSemaine(annee, mois, jour);
    const jourType = types.get(semaine);
    if (jourType) {
      jours.push({ jour, type: jourType.type, heures_prevues: jourType.heures_prevues });
      continue;
    }
    jours.push(
      existant ?? {
        jour,
        type: semaine === 0 || semaine === 6 ? 'weekend' : 'travail',
        heures_prevues: null,
      }
    );
  }
  return { jours, feriesGardes, absencesGardees };
}

/** « 1 jour férié gardé. 2 jours d'absence gardés. » (vide s'il n'y en a pas). */
export function noteJoursGardes(feries: number, absences: number): string {
  let note = '';
  if (feries > 0) {
    note += ` ${pluriel(feries, 'jour férié', 'jours fériés')} ${accord(feries, 'gardé')}.`;
  }
  if (absences > 0) {
    note += ` ${pluriel(absences, 'jour')} d'absence ${accord(absences, 'gardé')}.`;
  }
  return note;
}
