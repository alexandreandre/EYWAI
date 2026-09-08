/**
 * Lignes du brut qui proviennent d'une saisie mensuelle (page Primes), par
 * opposition à celles que le moteur déduit du contrat ou du calendrier.
 *
 * Pourquoi c'est utile : l'écran d'édition d'un bulletin ne recalcule ni les
 * cotisations ni le net. Corriger une heure supplémentaire directement sur le
 * bulletin produit donc un document incohérent. Ces lignes-là se corrigent à
 * la source — la variable du mois — puis le bulletin se régénère.
 *
 * La reconnaissance se fait sur le libellé : les lignes du bulletin ne portent
 * pas de clé stable (`calcul_brut.py` ne pose qu'un `libelle`), et les
 * bulletins déjà produits ne peuvent pas en gagner une rétroactivement. Un
 * faux négatif ne coûte qu'un lien manquant, jamais un blocage : le champ
 * reste éditable dans tous les cas.
 */

/** HS conjoncturelles (`Heures suppl. majorées à 25%`), hors structurelles. */
const HEURES_SUPP = /heures\s+suppl/i;

/** Les structurelles viennent du contrat, pas d'une saisie du mois. */
const STRUCTURELLES = /structurelle/i;

/** Paniers et leur réintégration (`Panier repas`, `Réintégration panier …`). */
const PANIER = /panier/i;

export function estLigneDeVariableMensuelle(libelle: string | undefined | null): boolean {
  if (!libelle) return false;
  if (PANIER.test(libelle)) return true;
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
