/**
 * Indemnité conventionnelle d'un licenciement, d'un départ ou d'une mise à la
 * retraite, saisie sur le départ (pas de barème conventionnel extrait).
 *
 * BOSS « Indemnités de rupture » : l'indemnité légale est un minimum, une
 * indemnité conventionnelle plus favorable la remplace (§ 280, 1550, 1630) ; le
 * montant prévu par la convention collective de branche est le seuil de la
 * CSG/CRDS et le troisième critère des limites d'exonération (§ 80, 300, 360,
 * 1640, 1650). La valeur est rangée dans `exit_notes.indemnite_conventionnelle`.
 */
import type { ExitType } from '@/api/employeeExits';
import type { InitiativeRetraite } from './retraite';

export const LIBELLE_INDEMNITE_CONVENTIONNELLE = 'Indemnité conventionnelle de branche (€)';

export function indemniteConventionnelleSaisissable(exitType: ExitType): boolean {
  return exitType === 'licenciement' || exitType === 'depart_retraite';
}

const SOURCE =
  'Montant prévu par la convention collective de branche ou un accord professionnel ou interprofessionnel. ' +
  'Martine verse le plus élevé de ce montant et du minimum légal.';

export function aideIndemniteConventionnelle(
  exitType: ExitType,
  initiative: InitiativeRetraite = 'employee'
): string {
  if (exitType === 'depart_retraite' && initiative === 'employee') {
    return (
      `${SOURCE} Une indemnité de départ volontaire à la retraite est soumise aux cotisations pour ` +
      'tout son montant. Vide : minimum légal.'
    );
  }
  return (
    `${SOURCE} Ce montant est retenu comme minimum conventionnel de branche pour la CSG/CRDS et les ` +
    "limites d'exonération (BOSS, Indemnités de rupture). Vide : minimum légal."
  );
}
