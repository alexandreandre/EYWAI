/**
 * Jour « absent, type à donner » (case « absent » de l'import de pointages,
 * retour d'Elsa du 28/10/2026). Le serveur porte la marque dans le type du
 * jour prévu ; elle ne retire rien du salaire et bloque la génération, sans
 * forçage, tant que la RH n'a pas donné le type (congé, RTT, arrêt ou absence
 * non payée). Toutes les vues la montrent en rouge.
 */

export const TYPE_ABSENT_A_TYPER = 'absent_a_typer';

export function estAbsentATyper(jour: { type?: string | null } | null | undefined): boolean {
  return jour?.type === TYPE_ABSENT_A_TYPER;
}

export function joursAbsentsATyper(
  prevu: ReadonlyArray<{ jour: number; type?: string | null }>
): number[] {
  return prevu
    .filter(estAbsentATyper)
    .map((j) => j.jour)
    .sort((a, b) => a - b);
}

function enumerer(elements: string[]): string {
  if (elements.length <= 1) return elements.join('');
  return `${elements.slice(0, -1).join(', ')} et ${elements[elements.length - 1]}`;
}

/** « 2 jours absents sans type (les 9 et 11) ». */
export function phraseAbsentsATyper(jours: number[]): string {
  const n = jours.length;
  const quand = `${n === 1 ? 'le' : 'les'} ${enumerer(jours.map(String))}`;
  return n === 1
    ? `1 jour absent sans type (${quand})`
    : `${n} jours absents sans type (${quand})`;
}

export function aDesAbsentsATyper(row: { joursAbsentsATyper?: number[] | null }): boolean {
  return (row.joursAbsentsATyper?.length ?? 0) > 0;
}

/**
 * Filtre de saisie de la page Calendrier : « À saisir » garde aussi un salarié
 * dont un jour est marqué absent sans type (la paie est bloquée tant qu'il
 * n'est pas typé) ; les autres filtres suivent le statut.
 */
export function correspondAuFiltreSaisie(
  row: { rowStatus: string; joursAbsentsATyper?: number[] | null },
  filtre: string
): boolean {
  if (filtre === 'all') return true;
  if (filtre === 'a_saisir' && aDesAbsentsATyper(row)) return true;
  return row.rowStatus === filtre;
}

export interface AbsentsDuCalendrier {
  id: string;
  nom: string;
  jours: number[];
}

export function resumeAbsentsATyper(
  rows: readonly {
    employee: { id: string; first_name?: string | null; last_name?: string | null };
    joursAbsentsATyper?: number[] | null;
  }[]
): AbsentsDuCalendrier[] {
  return rows
    .filter(aDesAbsentsATyper)
    .map((r) => ({
      id: r.employee.id,
      nom: `${r.employee.first_name ?? ''} ${r.employee.last_name ?? ''}`.trim(),
      jours: [...(r.joursAbsentsATyper ?? [])],
    }));
}

/** La phrase du bandeau rouge de la page Calendrier. */
export function phraseBandeauAbsents(resume: AbsentsDuCalendrier[]): string | null {
  const total = resume.reduce((n, s) => n + s.jours.length, 0);
  if (total === 0) return null;
  const noms = resume.map((s) => s.nom).join(', ');
  const debut =
    total > 1
      ? `${total} jours sont marqués « absent » sans type (${noms}) : donnez-leur leur type dans le calendrier.`
      : `1 jour est marqué « absent » sans type (${noms}) : donnez-lui son type dans le calendrier.`;
  const fin =
    resume.length > 1
      ? 'La paie de ces salariés est refusée, sans forçage possible, jusque-là.'
      : 'La paie de ce salarié est refusée, sans forçage possible, jusque-là.';
  return `${debut} ${fin}`;
}
