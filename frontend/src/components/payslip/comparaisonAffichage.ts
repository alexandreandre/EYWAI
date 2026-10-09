/**
 * Textes de l'onglet de comparaison d'un bulletin : dates en clair, trace d'un
 * acquittement. Fonctions pures, testées à part de l'écran.
 */

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
