/** Les mots de l'onglet « Historique » : plafond de versions et restauration. */

/** Miroir de `VERSIONS_CONSERVEES` (backend/app/modules/payslips/domain/historique.py). */
export const VERSIONS_CONSERVEES = 10;

/** Ce que l'historique garde, et ce qui part quand il est plein. */
export function phraseConservation(numerosDeVersion: number[]): string {
  const base = `L'historique garde les ${VERSIONS_CONSERVEES} dernières versions.`;
  if (numerosDeVersion.length < VERSIONS_CONSERVEES) return base;
  const plusAncienne = Math.min(...numerosDeVersion);
  return `${base} Il est plein : à la prochaine modification, la version ${plusAncienne}, la plus ancienne, sera supprimée avec son PDF.`;
}

/** La restauration ne rétablit que les heures sup et les primes saisies. */
export const libelleBoutonRestaurer = 'Restaurer heures sup et primes';

export function textesConfirmationRestauration(version: number): {
  titre: string;
  description: string;
  confirmer: string;
} {
  return {
    titre: `Restaurer la version ${version} ?`,
    description:
      `Seuls les heures sup et les primes saisies de la version ${version} sont rétablies. ` +
      'Les autres informations du bulletin ne reviennent pas : notes, absences, salaire et cotisations sont ceux du moment. ' +
      'Le bulletin sera recalculé, et la version actuelle reste dans l’historique.',
    confirmer: 'Restaurer ces heures sup et ces primes',
  };
}
