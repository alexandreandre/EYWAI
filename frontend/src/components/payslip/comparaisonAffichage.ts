/**
 * Textes de l'onglet de comparaison d'un bulletin : dates en clair, trace d'un
 * acquittement. Fonctions pures, testées à part de l'écran.
 */

import { pluriel } from '@/lib/pluriel';

const MOIS = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

function partiesParis(iso: string | null | undefined): Intl.DateTimeFormatPart[] | null {
  if (!iso) return null;
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return null;
  return new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'Europe/Paris',
    day: 'numeric',
    month: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
}

/** « 22:26 », à l'heure de Paris ; chaîne vide si la date est illisible. */
export function heureParis(iso: string | null | undefined): string {
  const parties = partiesParis(iso);
  if (!parties) return '';
  const valeur = (type: string) => parties.find((p) => p.type === type)?.value ?? '';
  return `${valeur('hour')}:${valeur('minute')}`;
}

/** « 9 octobre 2026 », jour de Paris ; chaîne vide si la date est illisible. */
export function dateEnClair(iso: string | null | undefined): string {
  const parties = partiesParis(iso);
  if (!parties) return '';
  const valeur = (type: string) => parties.find((p) => p.type === type)?.value ?? '';
  const jour = Number(valeur('day'));
  return `${jour === 1 ? '1er' : jour} ${MOIS[Number(valeur('month')) - 1] ?? ''} ${valeur('year')}`;
}

/** « 7 octobre 2026 à 09:12 », à l'heure de Paris ; chaîne vide si la date est illisible. */
export function dateHeureEnClair(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const parties = new Intl.DateTimeFormat('fr-FR', {
    timeZone: 'Europe/Paris',
    day: 'numeric',
    month: 'numeric',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).formatToParts(date);
  const valeur = (type: string) => parties.find((p) => p.type === type)?.value ?? '';
  const jour = Number(valeur('day'));
  const mois = MOIS[Number(valeur('month')) - 1] ?? '';
  return `${jour === 1 ? '1er' : jour} ${mois} ${valeur('year')} à ${valeur('hour')}:${valeur('minute')}`;
}

type TraceAlerte = {
  status: 'active' | 'acquittee' | 'ignoree';
  acquitted_by?: string | null;
  acquitted_at?: string | null;
  comment?: string | null;
};

/** « Acquittée par Prénom Nom le 7 octobre 2026 à 09:12 · commentaire » ; vide si l'alerte est active. */
export function traceAlerte(alerte: TraceAlerte): string {
  if (alerte.status === 'active') return '';
  let trace = alerte.status === 'ignoree' ? 'Ignorée' : 'Acquittée';
  if (alerte.acquitted_by) trace += ` par ${alerte.acquitted_by}`;
  const quand = dateHeureEnClair(alerte.acquitted_at);
  if (quand) trace += ` le ${quand}`;
  if (alerte.comment) trace += ` · ${alerte.comment}`;
  return trace;
}

/** « 12,3 % » : une décimale, virgule, espace avant le signe. */
export function pourcentFr(valeur: number): string {
  return `${valeur.toFixed(1).replace('.', ',')} %`;
}

/**
 * La variation d'une alerte : un pourcentage pour des euros ou des heures, la
 * différence en lignes quand l'alerte compare deux nombres de lignes (« +1 ligne »).
 */
export function variationAffichee(alerte: {
  unite?: string | null;
  value_n: number;
  value_n1: number;
  delta_pct: number;
}): string {
  if (alerte.unite !== 'nombre') return pourcentFr(alerte.delta_pct);
  const ecart = alerte.value_n - alerte.value_n1;
  const signe = ecart > 0 ? '+' : ecart < 0 ? '−' : '';
  return `${signe}${pluriel(Math.abs(ecart), 'ligne')}`;
}

type NiveauAlerte = 'CRITIQUE' | 'AVERTISSEMENT' | 'INFO';

export const LIBELLE_NIVEAU: Record<NiveauAlerte, string> = {
  CRITIQUE: 'Critique',
  AVERTISSEMENT: 'Avertissement',
  INFO: 'Info',
};

/** R12 (« pas de bulletin précédent ») est dite par l'encadré dédié, pas deux fois. */
const REGLE_SANS_REFERENCE = 'R12';

/** Les alertes à lister : sans R12, et seulement le niveau filtré s'il y en a un. */
export function alertesAffichees<T extends { rule_id: string; level: NiveauAlerte }>(
  alertes: T[],
  niveau: NiveauAlerte | null
): T[] {
  return alertes.filter(
    (a) => a.rule_id !== REGLE_SANS_REFERENCE && (niveau === null || a.level === niveau)
  );
}

/** Alertes encore actives d'un niveau (R12 exclue, comme dans la liste). */
export function nombreActives<
  T extends { rule_id: string; level: NiveauAlerte; status: string },
>(alertes: T[], niveau: NiveauAlerte): number {
  return alertesAffichees(alertes, niveau).filter((a) => a.status === 'active').length;
}
