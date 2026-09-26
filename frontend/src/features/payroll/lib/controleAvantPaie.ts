/**
 * Contrôles avant paie : une vérification en panne ne vaut pas « rien à signaler ».
 *
 * Quand une requête de contrôle échoue, ses compteurs retombent à zéro : sans
 * garde, l'écran affichait alors « tout va bien » et le verrou « Lancer la
 * paie » s'ouvrait (constat C1 de l'audit du 25/09). Décision : rendre la panne
 * visible, sans bloquer durement la paie — la gestionnaire peut réessayer, ou
 * générer quand même après une confirmation explicite.
 */

import type { PreflightAnomaly } from '@/api/payrollPreflight';
import { countOpenBlockingAnomalies } from '@/features/payroll/components/preflightLabels';

export const MESSAGE_GENERER_SANS_CONTROLE =
  "Le contrôle avant paie n'a pas pu être vérifié. Générer quand même ?";

/**
 * Message de confirmation à montrer avant de générer, ou `null` s'il n'y a
 * rien à confirmer. Un contrôle en erreur se confirme toujours ; un contrôle
 * qui répond garde la règle d'avant (confirmation dès une anomalie bloquante
 * ouverte).
 */
export function messageConfirmationGeneration({
  controleEnErreur,
  anomalies,
}: {
  controleEnErreur: boolean;
  anomalies: PreflightAnomaly[];
}): string | null {
  if (controleEnErreur) return MESSAGE_GENERER_SANS_CONTROLE;
  const bloquantes = countOpenBlockingAnomalies(anomalies);
  if (bloquantes > 0) {
    return `${bloquantes} anomalie(s) bloquante(s) ouverte(s). Générer quand même les bulletins ?`;
  }
  return null;
}

/**
 * État du verrou « Lancer la paie » :
 * - `verification` : les compteurs du parcours sont en cours de chargement ;
 * - `indisponible` : un compteur n'a pas pu être lu — on ne sait pas s'il reste
 *   des étapes, le verrou ne s'ouvre donc pas en silence ;
 * - `etapes_en_attente` : au moins une étape a des actions à traiter ;
 * - `ouvert` : toutes les étapes suivies sont à zéro.
 *
 * La panne passe avant les étapes en attente : ce qu'il faut d'abord, c'est
 * réessayer, sans quoi les compteurs affichés ne sont pas complets.
 */
export type EtatVerrouPaie = 'verification' | 'indisponible' | 'etapes_en_attente' | 'ouvert';

export function etatVerrouPaie({
  enChargement,
  enErreur,
  compteurs,
}: {
  enChargement: boolean;
  enErreur: boolean;
  compteurs: readonly number[];
}): EtatVerrouPaie {
  if (enChargement) return 'verification';
  if (enErreur) return 'indisponible';
  return compteurs.every((n) => n === 0) ? 'ouvert' : 'etapes_en_attente';
}
