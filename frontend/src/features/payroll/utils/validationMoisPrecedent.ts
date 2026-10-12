/**
 * Valider un mois dont le mois précédent est à recalculer.
 *
 * Octobre part des cumuls de septembre. Septembre « À recalculer » (une prime
 * ajoutée après coup) : octobre se validait sans un mot, et ses cumuls
 * changeront au recalcul de septembre (relevé J.1). La validation n'est pas
 * bloquée — le bulletin d'octobre peut être juste — mais la fenêtre le dit.
 */

import { estPerime } from './bulletinARecalculer';
import { deDevant } from './elision';
import { monthYearLabel } from './payrollMonth';
import { moisPrecedent } from './revueDuMois';

type Ligne = {
  year: number;
  month: number;
  a_recalculer?: boolean | null;
  origine?: string | null;
  status?: string | null;
};

/** Le mois précédent s'il est à recalculer (brouillon ou validé), sinon null. */
export function moisPrecedentARecalculer(
  lignes: readonly Ligne[] | null | undefined,
  year: number,
  month: number
): { year: number; month: number } | null {
  const avant = moisPrecedent(year, month);
  const ligne = (lignes ?? []).find((l) => l.year === avant.year && l.month === avant.month);
  return ligne && estPerime(ligne) ? avant : null;
}

function enMinuscule(month: number, year: number): string {
  return monthYearLabel(month, year).toLowerCase();
}

/** « Septembre 2026 est à recalculer : les cumuls d'octobre 2026 peuvent changer. » */
export function avertissementMoisPrecedent(
  avant: { year: number; month: number },
  year: number,
  month: number
): string {
  return `${monthYearLabel(avant.month, avant.year)} est à recalculer : les cumuls ${deDevant(
    enMinuscule(month, year)
  )} peuvent changer.`;
}

/** La même phrase pour « Valider les bulletins prêts » : les salariés concernés, nommés. */
export function avertissementMoisPrecedentGroupe(
  noms: readonly string[],
  year: number,
  month: number
): string | null {
  if (noms.length === 0) return null;
  const avant = moisPrecedent(year, month);
  const qui =
    noms.length === 1 ? noms[0] : `${noms.length} salariés (${noms.join(', ')})`;
  const possessif = noms.length === 1 ? 'son' : 'leur';
  return `${monthYearLabel(avant.month, avant.year)} est à recalculer pour ${qui} : les cumuls de ${possessif} bulletin ${deDevant(
    enMinuscule(month, year)
  )} peuvent changer.`;
}
