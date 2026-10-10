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

export const LIBELLE_SOUMISE_COTISATIONS = 'Soumise à cotisations';
export const LIBELLE_SOUMISE_IMPOT = "Soumise à l'impôt";

/** Pastille d'une prime du bulletin : imprimée dans le brut (soumise) ou non. */
export function pastilleSoumise(soumise: boolean): string {
  return soumise ? LIBELLE_SOUMISE_COTISATIONS : 'Non soumise à cotisations';
}

/** Sous-titre de la liste des saisies : le mois réellement affiché. */
export function sousTitreSaisies(year: number, month: number, filtreSurUnSalarie: boolean): string {
  const mois = moisEnToutesLettres(year, month);
  return filtreSurUnSalarie
    ? `Saisies ponctuelles de ce salarié pour ${mois}.`
    : `Liste de toutes les saisies ponctuelles pour ${mois}.`;
}
