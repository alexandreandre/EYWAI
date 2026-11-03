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
