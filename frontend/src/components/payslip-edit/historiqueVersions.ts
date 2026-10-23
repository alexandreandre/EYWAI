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

/** Ce que restaurer une version ferait au bulletin du moment (calculé par le serveur). */
export interface ApercuRestauration {
  reviennent: string[];
  remplacees: string[];
  retirees: string[];
}

/** La restauration rétablit les variables du mois d'une version, et rien d'autre. */
export const PHRASE_RESTAURATION =
  'Restaurer une version rétablit ses heures sup, ses primes saisies, ses régularisations et ses lignes corrigées, ' +
  'et retire celles qu’elle n’avait pas, puis recalcule le bulletin. Le planning, les absences, la fiche du salarié ' +
  'et les notes restent ceux d’aujourd’hui. La version actuelle reste dans l’historique.';

export const libelleBoutonRestaurer = 'Restaurer heures sup, primes et corrections';

/**
 * L'intitulé d'une version : ce qu'elle contient, donc ce qui revient si on la
 * restaure. Il affichait le changement qui l'avait remplacée (« 1 prime
 * retirée » sur une version qui avait la prime, jeu du 23/10).
 */
export function intituleDeVersion(entree: { contenu?: string[] | null }): string {
  return entree.contenu?.length ? entree.contenu.join(' · ') : 'Contenu de cette version non lu.';
}

/** Le changement qui a remplacé la version, dit comme tel. */
export function remplaceePar(entree: { changes_summary: string }): string {
  return `Remplacée par : ${entree.changes_summary}`;
}

export function textesConfirmationRestauration(
  version: number,
  apercu: ApercuRestauration | null | undefined
): {
  titre: string;
  sections: Array<{ titre: string; lignes: string[] }>;
  rien: string | null;
  fin: string;
  confirmer: string;
} {
  const sections = apercu
    ? [
        { titre: 'Reviennent', lignes: apercu.reviennent },
        { titre: 'Seront remplacées', lignes: apercu.remplacees },
        { titre: 'Seront retirées', lignes: apercu.retirees },
      ].filter((section) => section.lignes.length > 0)
    : [];
  const rien = !apercu
    ? 'Le détail de ce qui revient n’a pas pu être lu. La restauration rétablit les heures sup, les primes saisies, ' +
      'les régularisations et les corrections de ligne de la version, et retire celles d’aujourd’hui qu’elle n’avait pas.'
    : sections.length === 0
      ? 'Rien ne change : cette version a déjà les mêmes heures sup, primes, régularisations et corrections que le bulletin.'
      : null;
  return {
    titre: `Restaurer la version ${version} ?`,
    sections,
    rien,
    fin:
      'Le planning, les absences, la fiche du salarié et les notes restent ceux d’aujourd’hui. ' +
      'Le bulletin sera recalculé, et la version actuelle reste dans l’historique.',
    confirmer: 'Restaurer ces heures sup, primes et corrections',
  };
}
