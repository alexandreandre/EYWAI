/**
 * Reconnaissance des lignes du brut selon ce qui se passe quand on les corrige.
 *
 * Les **heures supplémentaires conjoncturelles** sont le seul cas où corriger
 * la quantité sur le bulletin suffit : à l'enregistrement, le serveur les
 * redonne au moteur, qui refait le brut, les cotisations et le net. Toutes les
 * autres lignes ne changent que le brut — cotisations et net restent ceux du
 * calcul d'origine, et il faut le dire.
 *
 * Sont écartées :
 * - les heures supplémentaires **structurelles**, qui viennent de l'horaire
 *   contractuel (39 h) et non d'une variable du mois ;
 * - les heures **complémentaires** du temps partiel, autre régime.
 *
 * La reconnaissance se fait sur le libellé : les lignes du bulletin ne portent
 * pas de clé stable (`calcul_brut.py` ne pose qu'un `libelle`) et les bulletins
 * déjà produits ne peuvent pas en gagner une rétroactivement. Le même choix est
 * fait côté serveur (`payslips/domain/heures_sup.py`) — les deux doivent rester
 * d'accord, sinon l'écran promettrait un recalcul qui n'aura pas lieu.
 */

const HEURES_SUPP = /heures\s+suppl/i;
const STRUCTURELLES = /structurelle/i;

/** Ligne dont la correction déclenche un recalcul complet à l'enregistrement. */
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
