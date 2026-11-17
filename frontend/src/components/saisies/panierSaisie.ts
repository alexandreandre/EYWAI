import type { SituationRepas } from '@/lib/situationsRepas';

/** Panier ou repas : le nombre d'unités compte pour l'exonération. */
export function estUnPanier(nom: string): boolean {
  return /panier|repas/i.test(nom);
}

/** Le libellé dit lui-même « soumis » (« Prime panier soumises »), hors « non soumis ». */
function ditSoumis(nom: string): boolean {
  return /soumis/i.test(nom) && !/non[\s-]*soumis/i.test(nom);
}

/**
 * Un nom tapé à la main qui désigne un panier exonéré : par défaut non soumis.
 * Un repas en avantage en nature reste soumis, comme un libellé qui dit « soumis ».
 */
export function panierNonSoumisParDefaut(nom: string): boolean {
  return estUnPanier(nom) && !ditSoumis(nom) && !/avantage|en nature/i.test(nom);
}

/**
 * Cases « soumise » par défaut quand le nom tapé change. Elles ne bougent que si le
 * nom passe d'un panier exonéré à autre chose (ou l'inverse) : un choix fait à la
 * main sur les cases reste tant que le nom garde la même nature.
 */
export function casesApresNouveauNom(
  ancienNom: string,
  nouveauNom: string,
  cases: { is_socially_taxed: boolean; is_taxable: boolean },
): { is_socially_taxed: boolean; is_taxable: boolean } {
  const avant = panierNonSoumisParDefaut(ancienNom);
  const apres = panierNonSoumisParDefaut(nouveauNom);
  if (avant === apres) return cases;
  return { is_socially_taxed: !apres, is_taxable: !apres };
}

/** Le bloc « Nombre de paniers » n'a de sens que pour un panier non soumis payé au brut. */
export function afficherBlocPanier(nom: string, champs: { is_socially_taxed: boolean; sur_le_net?: boolean }): boolean {
  return estUnPanier(nom) && !champs.is_socially_taxed && !champs.sur_le_net;
}

/** Nombre et situation du repas : envoyés seulement pour un panier non soumis (le moteur les ignore sinon). */
export function champsDuPanier(
  nom: string,
  champs: { is_socially_taxed: boolean; sur_le_net?: boolean },
  nombre: number | '',
  situation: SituationRepas,
): { payroll_quantity?: number; quantity_kind?: 'count'; situation_repas?: SituationRepas } {
  if (!afficherBlocPanier(nom, champs)) return {};
  return {
    ...(typeof nombre === 'number' && nombre > 0 ? { payroll_quantity: nombre, quantity_kind: 'count' as const } : {}),
    situation_repas: situation,
  };
}
