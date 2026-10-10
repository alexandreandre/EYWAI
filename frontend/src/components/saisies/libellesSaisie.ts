/**
 * Les mots des saisies du mois, écrits une seule fois : la page des primes, le
 * tableau, la fenêtre de saisie et les pastilles du bulletin disent la même chose.
 */

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
];

/** « octobre 2026 ». */
export function moisEnToutesLettres(year: number, month: number): string {
  return `${MOIS[month - 1] ?? ''} ${year}`.trim();
}

/** Ce que la fenêtre de saisie dit de la portée d'une saisie ouverte depuis un bulletin. */
export function phraseSaisiePonctuelle(year?: number, month?: number): string {
  if (!year || !month) return 'Cette saisie ponctuelle ne vaut que pour le mois du bulletin.';
  return `Cette saisie ponctuelle ne vaut que pour ${moisEnToutesLettres(year, month)}.`;
}
