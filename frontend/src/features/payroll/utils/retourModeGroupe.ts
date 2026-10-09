/**
 * Fermer le Mode Groupé (Échap, croix, Annuler) ramène d'où l'on vient. Le
 * « retour arrière » du navigateur envoyait au tableau de bord quand la page
 * avait été ouverte par son adresse (constat du 09/10) : l'origine voyage dans
 * l'état de navigation, et à défaut on revient à la page Paie.
 */

export const PAGE_PAIE = '/payroll';
const MODE_GROUPE = '/payroll/generate';

/** L'état de navigation à poser sur le lien qui ouvre le Mode Groupé. */
export function etatPourModeGroupe(ici: { pathname: string; search: string }): { depuis: string } {
  return { depuis: `${ici.pathname}${ici.search}` };
}

export function destinationDeFermeture(etat: unknown): string {
  const depuis = (etat as { depuis?: unknown } | null | undefined)?.depuis;
  if (typeof depuis !== 'string') return PAGE_PAIE;
  if (!depuis.startsWith('/') || depuis.startsWith('//')) return PAGE_PAIE;
  if (depuis === MODE_GROUPE || depuis.startsWith(`${MODE_GROUPE}?`)) return PAGE_PAIE;
  return depuis;
}
