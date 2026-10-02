/**
 * Heures réelles qu'un enregistrement n'a pas gardées.
 *
 * Le serveur remet à 0 le réel d'un jour typé arrêt ou absence
 * (`normalize_actual_hours_on_absence_days`). L'écran gardait les heures
 * saisies jusqu'au rechargement, sans un mot : il reprend maintenant ce qui est
 * enregistré et dit quels jours ont perdu leurs heures.
 */
import type { ActualHoursData } from '@/api/calendar';

type Jour = Pick<ActualHoursData, 'jour' | 'heures_faites'>;

export function joursAuxHeuresRetirees(envoye: readonly Jour[], relu: readonly Jour[]): number[] {
  const gardees = new Map(relu.map((j) => [j.jour, Number(j.heures_faites) || 0]));
  return envoye
    .filter((j) => (Number(j.heures_faites) || 0) > 0 && (gardees.get(j.jour) ?? 0) === 0)
    .map((j) => j.jour)
    .sort((a, b) => a - b);
}

export function avecLeReelEnregistre<T extends Jour>(affiche: readonly T[], relu: readonly Jour[]): T[] {
  const gardees = new Map(relu.map((j) => [j.jour, j.heures_faites]));
  return affiche.map((j) => (gardees.has(j.jour) ? { ...j, heures_faites: gardees.get(j.jour) ?? null } : j));
}

function enumerer(jours: readonly number[]): string {
  const noms = jours.map((j) => (j === 1 ? '1er' : String(j)));
  return noms.length <= 1 ? noms.join('') : `${noms.slice(0, -1).join(', ')} et ${noms[noms.length - 1]}`;
}

export function messageHeuresRetirees(jours: readonly number[]): string {
  const sujet = jours.length > 1 ? `Les ${enumerer(jours)} sont des jours` : `Le ${enumerer(jours)} est un jour`;
  return (
    `${sujet} d’arrêt ou d’absence : les heures saisies n’ont pas été gardées. ` +
    'Si la personne a travaillé, changez d’abord le type du jour.'
  );
}
