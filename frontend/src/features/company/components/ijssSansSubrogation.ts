/**
 * Réglage « sans subrogation : IJSS déduites ou non » (conception du 23/10/2026).
 *
 * Sans subrogation, la CPAM verse les IJSS au salarié. La société choisit de
 * verser le salaire garanti en entier, ou seulement le complément, IJSS des
 * jours maintenus déduites (règle légale).
 */

export type ChoixIjssSansSubrogation = 'garanti' | 'complement';

export const CHOIX_IJSS_SANS_SUBROGATION: ReadonlyArray<{
  valeur: ChoixIjssSansSubrogation;
  libelle: string;
  deduire: boolean;
}> = [
  { valeur: 'garanti', libelle: 'Verser le salaire garanti en entier', deduire: false },
  {
    valeur: 'complement',
    libelle: 'Verser le complément, IJSS déduites (règle légale)',
    deduire: true,
  },
];

export const AIDE_IJSS_SANS_SUBROGATION =
  'Sans subrogation, la CPAM paie les IJSS directement au salarié. Martine peut les déduire du maintien, comme le prévoit la loi, ou verser le salaire garanti en entier.';

export function choixIjssDepuisReglage(deduire: boolean): ChoixIjssSansSubrogation {
  return deduire ? 'complement' : 'garanti';
}

export function reglageDepuisChoixIjss(valeur: string): boolean | null {
  const choix = CHOIX_IJSS_SANS_SUBROGATION.find((c) => c.valeur === valeur);
  return choix ? choix.deduire : null;
}
