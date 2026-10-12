/**
 * Rupture conventionnelle d'un salarié en droit de bénéficier d'une pension de
 * retraite d'un régime légalement obligatoire.
 *
 * BOSS « Indemnités de rupture », § 940 : l'indemnité est alors « soumise à
 * l'impôt sur le revenu dès le premier euro » ; § 60 et 890 : son régime social
 * (cotisations, CSG/CRDS, contribution patronale de 40 %) ne dépend plus de ce
 * droit depuis 2023. Rangée dans `exit_notes.pension_liquidable`.
 */
export const LIBELLE_PENSION_LIQUIDABLE = 'Le salarié peut liquider une pension de retraite de base';

export const AIDE_PENSION_LIQUIDABLE =
  "L'indemnité est alors imposable dès le premier euro ; ses cotisations, sa CSG/CRDS et la " +
  'contribution patronale de 40 % ne changent pas (BOSS, Indemnités de rupture, § 60, 890 et 940).';
