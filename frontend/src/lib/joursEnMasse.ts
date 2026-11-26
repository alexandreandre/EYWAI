/**
 * Jours choisis pour l'activité partielle en masse (26/11, LEWIS : « tous les
 * vendredis du 01/12 au 31/12 »). Une période « du … au … » et des jours de la
 * semaine cochés donnent des dates ; des dates cliquées une à une s'y
 * ajoutent. Dates au format ISO (AAAA-MM-JJ), sans fuseau : le jour du
 * calendrier, jamais une heure.
 */

/** Jours de la semaine, lundi d'abord : l'indice est celui des cases (0 = lundi). */
export const JOURS_DE_LA_SEMAINE = ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim'] as const;

export const NOMS_DES_JOURS = [
  'lundi',
  'mardi',
  'mercredi',
  'jeudi',
  'vendredi',
  'samedi',
  'dimanche',
] as const;

export interface ChoixDesJours {
  /** Début de la période, AAAA-MM-JJ (vide : pas de période). */
  du: string;
  /** Fin de la période, AAAA-MM-JJ, incluse. */
  au: string;
  /** Jours de la semaine cochés : 0 = lundi … 6 = dimanche. */
  joursSemaine: readonly number[];
  /** Dates cliquées une à une, AAAA-MM-JJ. */
  datesCliquees: readonly string[];
}

const ISO = /^\d{4}-\d{2}-\d{2}$/;

/** Une date AAAA-MM-JJ valide, en UTC (aucun décalage d'heure d'été). */
function lireIso(valeur: string): Date | null {
  if (!ISO.test(valeur)) return null;
  const [a, m, j] = valeur.split('-').map(Number);
  const d = new Date(Date.UTC(a, m - 1, j));
  return d.getUTCFullYear() === a && d.getUTCMonth() === m - 1 && d.getUTCDate() === j ? d : null;
}

function versIso(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Jour de la semaine d'une date, lundi = 0. */
export function jourDeLaSemaine(iso: string): number | null {
  const d = lireIso(iso);
  return d ? (d.getUTCDay() + 6) % 7 : null;
}

/** Le défaut de la période : rien, ou la fin avant le début. */
export function erreurDePeriode(du: string, au: string): string | null {
  if (!du && !au) return null;
  if (!du || !au) return 'Indiquez le début et la fin de la période.';
  const debut = lireIso(du);
  const fin = lireIso(au);
  if (!debut || !fin) return 'Date de période illisible.';
  if (fin < debut) return 'La fin de la période est avant son début.';
  return null;
}

/** Les dates retenues, triées et sans doublon. */
export function datesRetenues(choix: ChoixDesJours): string[] {
  const dates = new Set<string>();
  const debut = lireIso(choix.du);
  const fin = lireIso(choix.au);
  const jours = new Set(choix.joursSemaine);
  if (debut && fin && fin >= debut && jours.size > 0) {
    for (let d = new Date(debut); d <= fin; d.setUTCDate(d.getUTCDate() + 1)) {
      if (jours.has((d.getUTCDay() + 6) % 7)) dates.add(versIso(d));
    }
  }
  for (const iso of choix.datesCliquees) {
    if (lireIso(iso)) dates.add(iso);
  }
  return [...dates].sort();
}

/** Les mois (année, mois) couverts par des dates ISO, dans l'ordre. */
export function moisDesDates(dates: readonly string[]): { year: number; month: number }[] {
  const cles = [...new Set(dates.map((d) => d.slice(0, 7)))].sort();
  return cles.map((cle) => ({ year: Number(cle.slice(0, 4)), month: Number(cle.slice(5, 7)) }));
}

/** « ven. 04/12/2026 » : la date telle que l'écran la montre. */
export function dateCourte(iso: string): string {
  const j = jourDeLaSemaine(iso);
  const [a, m, d] = iso.split('-');
  return `${j == null ? '' : `${JOURS_DE_LA_SEMAINE[j]}. `}${d}/${m}/${a}`;
}

/** Une date cliquée au calendrier (objet Date local) en AAAA-MM-JJ. */
export function isoDuJourLocal(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const j = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${j}`;
}

/** Une date AAAA-MM-JJ en objet Date local (minuit), pour le calendrier. */
export function jourLocalDeIso(iso: string): Date {
  const [a, m, j] = iso.split('-').map(Number);
  return new Date(a, m - 1, j);
}
