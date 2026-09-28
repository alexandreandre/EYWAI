/**
 * Lignes du bulletin et liens vers les écrans où elles se corrigent.
 *
 * Les **heures supplémentaires conjoncturelles** se reconnaissent au libellé
 * (« Heures suppl. », hors structurelles) : les lignes du bulletin ne portent
 * pas de clé stable. Le même choix est fait côté serveur
 * (`payslips/domain/heures_sup.py`) — les deux doivent rester d'accord.
 *
 * Sont écartées :
 * - les heures supplémentaires **structurelles**, qui viennent de l'horaire
 *   contractuel (39 h) et non d'une variable du mois ;
 * - les heures **complémentaires** du temps partiel, autre régime.
 */

const HEURES_SUPP = /heures\s+suppl/i;
const STRUCTURELLES = /structurelle/i;

/** Ligne d'heures supplémentaires conjoncturelles (corrigeable depuis le bulletin). */
export function estLigneHeuresSupConjoncturelle(
  libelle: string | undefined | null
): boolean {
  if (!libelle) return false;
  return HEURES_SUPP.test(libelle) && !STRUCTURELLES.test(libelle);
}

/** Lien vers la page Primes, positionnée sur le mois (et le salarié) du bulletin. */
export function lienVariablesDuMois({
  employeeId,
  year,
  month,
}: {
  employeeId?: string;
  year: number;
  month: number;
}): string {
  const params = new URLSearchParams({ year: String(year), month: String(month) });
  if (employeeId) params.set('employee', employeeId);
  return `/saisies?${params.toString()}`;
}
