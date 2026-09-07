/**
 * Nom d'affichage d'un salarié — source unique.
 *
 * Règle française : le nom d'USAGE (marital…) prime à l'affichage quand il
 * existe (employees.nom_usage, source DSN S21.G00.30.003) ; sinon le nom de
 * naissance (last_name). Ex. Gaëlle KEWITZ, usage BOUALI → « BOUALI Gaëlle ».
 *
 * Ne JAMAIS utiliser pour : la DSN (nom de naissance obligatoire en 30.002),
 * les rapprochements d'imports, les identifiants ou chemins de stockage.
 */

export type NamedEmployee = {
  first_name?: string | null;
  last_name?: string | null;
  nom_usage?: string | null;
};

export const displayLastName = (e: NamedEmployee): string =>
  e.nom_usage?.trim() || e.last_name || '';

export const displayNameNomPrenom = (e: NamedEmployee): string =>
  `${displayLastName(e)} ${e.first_name ?? ''}`.trim();

export const displayNamePrenomNom = (e: NamedEmployee): string =>
  `${e.first_name ?? ''} ${displayLastName(e)}`.trim();

/** Chaîne de recherche : couvre nom d'usage ET nom de naissance. */
export const searchableName = (e: NamedEmployee): string =>
  `${e.first_name ?? ''} ${e.last_name ?? ''} ${e.nom_usage ?? ''}`.trim();
