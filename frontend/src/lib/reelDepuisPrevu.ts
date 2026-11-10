/**
 * « Réel = prévu » : ne complète que les jours prévus sans heures réelles.
 *
 * L'action réécrivait chaque jour du mois : un 6 h corrigé à la main repassait
 * à 7 h, des heures importées étaient écrasées, les week-ends passaient à 0 h
 * (constat du 08/10/2026). Désormais toute heure réelle déjà saisie est gardée,
 * et seul un jour de travail avec un prévu chiffré (0 h compris) est rempli.
 */
import type { ActualHoursData, PlannedEventData } from '@/api/calendar';

export interface ReelCompleté {
  actual: ActualHoursData[];
  completes: number;
  gardes: number;
}

const estTravail = (type: string | null | undefined) => type === 'travail' || type === 'work';

export interface OptionsReelDepuisPrevu {
  /** Forfait jours : le réel se pose en jours (1 ou 0), quelle que soit l'unité du prévu. */
  forfaitJours?: boolean;
  /** Dernier jour du contrat dans le mois : rien n'est écrit après. */
  dernierJour?: number | null;
}

export function completerReelDepuisPrevu(
  planned: PlannedEventData[],
  actual: ActualHoursData[],
  options: OptionsReelDepuisPrevu = {},
): ReelCompleté {
  const { forfaitJours = false, dernierJour = null } = options;
  const saisis = new Map<number, ActualHoursData>();
  for (const a of actual) {
    if (a.heures_faites !== null && a.heures_faites !== undefined) saisis.set(a.jour, a);
  }
  const resultat = new Map(saisis);
  let completes = 0;
  let gardes = 0;
  for (const p of planned) {
    // Un jour de travail prévu à 0 h se recopie comme les autres (retour du
    // 10/11 : il restait vide et il fallait repasser mettre 0).
    if (!estTravail(p.type) || !(typeof p.heures_prevues === 'number' && p.heures_prevues >= 0)) {
      continue;
    }
    if (dernierJour != null && p.jour > dernierJour) continue;
    if (saisis.has(p.jour)) {
      gardes += 1;
      continue;
    }
    const heures = forfaitJours ? (p.heures_prevues > 0 ? 1 : 0) : p.heures_prevues;
    resultat.set(p.jour, { jour: p.jour, type: p.type, heures_faites: heures });
    completes += 1;
  }
  return {
    actual: [...resultat.values()].sort((a, b) => a.jour - b.jour),
    completes,
    gardes,
  };
}

const pluriel = (n: number, un: string, plusieurs: string) => `${n} ${n > 1 ? plusieurs : un}`;

export function messageReelDepuisPrevu(salaries: number, completes: number, gardes: number): string {
  const debut = `Réel = prévu pour ${pluriel(salaries, 'salarié', 'salariés')} : ${pluriel(completes, 'jour complété', 'jours complétés')}`;
  return gardes > 0
    ? `${debut}, ${pluriel(gardes, 'jour déjà saisi gardé', 'jours déjà saisis gardés')}.`
    : `${debut}.`;
}
