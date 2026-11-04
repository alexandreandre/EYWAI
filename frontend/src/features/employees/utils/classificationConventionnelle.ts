/**
 * Classification conventionnelle d'une fiche : jamais de valeur mise d'office.
 *
 * Le formulaire de création partait de « Groupe C / classe 6 / coefficient 240 »,
 * prenait la première ligne de la grille, ou la classification « habituelle » de
 * la société, au groupe « C » et à la classe recopiée du coefficient : des fiches
 * se sont retrouvées en « Groupe C - Classe 700 - Coeff. 700 » sans que la RH
 * l'ait choisi (retour du 03/11). Le moteur lit la classe (prime d'ancienneté et
 * minima de la métallurgie) : une valeur d'office change la paie sans le dire.
 *
 * Ici : le départ est vide, la RH choisit, et un coefficient seul se range en
 * « Non précisé » / classe 0, comme la grille de la plasturgie.
 */
import { z } from 'zod';

export const GROUPE_NON_PRECISE = 'Non précisé';
export const MESSAGE_CLASSIFICATION_REQUISE = 'Classification conventionnelle requise.';

export type Classification = { groupe_emploi: string; classe_emploi: number; coefficient: number };

/** Ce que portent les champs du formulaire : un nombre absent vaut `undefined` (ou ''). */
export type ClassificationSaisie = {
  groupe_emploi?: string | null;
  classe_emploi?: number | string | null;
  coefficient?: number | string | null;
};

export const CLASSIFICATION_VIDE: { groupe_emploi: string; classe_emploi?: number; coefficient?: number } = {
  groupe_emploi: '',
  classe_emploi: undefined,
  coefficient: undefined,
};

/** Un entier lu dans un champ ; `undefined` s'il est vide ou illisible. */
function entier(valeur: unknown): number | undefined {
  if (valeur === null || valeur === undefined) return undefined;
  if (typeof valeur === 'string' && !valeur.trim()) return undefined;
  const n = Number(valeur);
  return Number.isFinite(n) ? n : undefined;
}

function groupe(c: ClassificationSaisie | null | undefined): string {
  return (c?.groupe_emploi ?? '').trim();
}

function coefficient(c: ClassificationSaisie | null | undefined): number | undefined {
  const n = entier(c?.coefficient);
  return n !== undefined && n > 0 ? n : undefined;
}

export function estClassificationVide(c: ClassificationSaisie | null | undefined): boolean {
  return !groupe(c) && entier(c?.classe_emploi) === undefined && coefficient(c) === undefined;
}

export function cleClassification(c: ClassificationSaisie): string {
  return `${groupe(c)}-${entier(c.classe_emploi) ?? ''}-${coefficient(c) ?? ''}`;
}

/** La valeur de la liste ; `undefined` quand rien n'est choisi, pour afficher « Choisir une classification ». */
export function valeurDuChoix(c: ClassificationSaisie | null | undefined): string | undefined {
  return c && !estClassificationVide(c) ? cleClassification(c) : undefined;
}

/** La classification gardée quand la grille arrive : celle choisie si la grille la connaît, sinon rien. */
export function classificationGardee<T extends ClassificationSaisie>(
  courante: T | null | undefined,
  grille: readonly ClassificationSaisie[],
): T | typeof CLASSIFICATION_VIDE {
  if (!courante || estClassificationVide(courante)) return CLASSIFICATION_VIDE;
  const cle = cleClassification(courante);
  return grille.some((c) => cleClassification(c) === cle) ? courante : CLASSIFICATION_VIDE;
}

function aCoefficientSeul(grille: readonly ClassificationSaisie[]): boolean {
  return (
    grille.length > 0 &&
    grille.every((c) => groupe(c) === GROUPE_NON_PRECISE && (entier(c.classe_emploi) ?? 0) === 0)
  );
}

/**
 * La grille de la convention, plus la classification que portent déjà les
 * salariés de la société si la grille ne la connaît pas. Elle est proposée, jamais
 * choisie d'office. Sous une grille à coefficient seul (plasturgie), elle y est
 * ramenée : « Non précisé », classe 0, son coefficient.
 */
export function grilleAvecClassificationHabituelle<T extends Classification>(
  grille: readonly T[],
  habituelle: ClassificationSaisie | null | undefined,
): Classification[] {
  const coeff = coefficient(habituelle);
  if (!habituelle || coeff === undefined) return [...grille];
  const proposee: Classification = aCoefficientSeul(grille)
    ? { groupe_emploi: GROUPE_NON_PRECISE, classe_emploi: 0, coefficient: coeff }
    : {
        groupe_emploi: groupe(habituelle) || GROUPE_NON_PRECISE,
        classe_emploi: entier(habituelle.classe_emploi) ?? 0,
        coefficient: coeff,
      };
  const cle = cleClassification(proposee);
  return grille.some((c) => cleClassification(c) === cle) ? [...grille] : [...grille, proposee];
}

/** « Coeff. 700 » quand ni groupe ni classe ne sont précisés ; « Groupe C - Classe 5 - Coeff. 170 » sinon. */
export function libelleClassification(c: ClassificationSaisie): string {
  const g = groupe(c);
  const classe = entier(c.classe_emploi);
  const coeff = coefficient(c);
  const sansGroupe = !g || g === GROUPE_NON_PRECISE;
  if (sansGroupe && (classe ?? 0) === 0) return coeff !== undefined ? `Coeff. ${coeff}` : GROUPE_NON_PRECISE;
  const parties = [
    g ? `Groupe ${g}` : null,
    classe !== undefined ? `Classe ${classe}` : null,
    coeff !== undefined ? `Coeff. ${coeff}` : null,
  ];
  return parties.filter(Boolean).join(' - ');
}

/**
 * La classification envoyée : rien si rien n'est saisi ; un coefficient sans
 * groupe se range en « Non précisé », classe 0 ; une classe absente n'est pas
 * inventée.
 */
export function classificationPourEnvoi(c: ClassificationSaisie | null | undefined): Record<string, unknown> {
  if (!c || estClassificationVide(c)) return {};
  const g = groupe(c);
  const classe = entier(c.classe_emploi);
  const coeff = coefficient(c);
  if (!g && coeff !== undefined) {
    return { groupe_emploi: GROUPE_NON_PRECISE, classe_emploi: classe ?? 0, coefficient: coeff };
  }
  const envoi: Record<string, unknown> = {};
  if (g) envoi.groupe_emploi = g;
  if (classe !== undefined) envoi.classe_emploi = classe;
  if (coeff !== undefined) envoi.coefficient = coeff;
  return envoi;
}

/** Un nombre entier facultatif : un champ vide reste vide, il ne devient pas 0. */
const entierFacultatif = (message: string) =>
  z.preprocess(
    (v) => (v === '' || v === null || v === undefined ? undefined : v),
    z.coerce.number({ invalid_type_error: message }).int({ message }).optional(),
  );

/** Les trois champs de la classification, tous facultatifs : la règle dépend de la convention. */
export const classificationSaisieSchema = z.object({
  groupe_emploi: z.string().optional().default(''),
  classe_emploi: entierFacultatif('La classe est un nombre entier.'),
  coefficient: entierFacultatif('Le coefficient est un nombre entier.').refine(
    (v) => v === undefined || v > 0,
    { message: 'Le coefficient est un nombre positif.' },
  ),
});

/** Avec une convention, il faut au moins un coefficient (le groupe peut rester « Non précisé »). */
export function classificationManquante(
  conventionChoisie: string | null | undefined,
  c: ClassificationSaisie | null | undefined,
): boolean {
  const avecConvention = Boolean(conventionChoisie && conventionChoisie !== '__aucune__');
  return avecConvention && coefficient(c) === undefined;
}
