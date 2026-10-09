/**
 * Accord en nombre des textes montrés à l'écran (« 1 jour », « 2 jours »).
 * Le singulier vaut pour 0 et 1 (« 0 jour », « 1,5 jour »), le pluriel dès 2.
 * Pendant côté serveur : backend/app/shared/domain/pluriel.py.
 */

/** Le mot seul, accordé : `accord(3, 'conservé')` → « conservés ». */
export function accord(n: number, un: string, plusieurs?: string): string {
  return n < 2 ? un : (plusieurs ?? `${un}s`);
}

/** Le nombre suivi du mot accordé : `pluriel(2, 'jour')` → « 2 jours ». */
export function pluriel(n: number, un: string, plusieurs?: string): string {
  const nombre = Number.isInteger(n) ? String(n) : n.toLocaleString('fr-FR');
  return `${nombre} ${accord(n, un, plusieurs)}`;
}
