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
  // Seulement les deux cases : l'appelant étale ce résultat dans tout le formulaire.
  if (avant === apres) return { is_socially_taxed: cases.is_socially_taxed, is_taxable: cases.is_taxable };
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

/**
 * Primes du mois : le nombre de paniers d'une saisie se corrige comme le montant
 * (L19, 27/11). Un montant changé seul garde la réintégration calculée sur
 * l'ancien nombre. Pas pour une valeur unitaire (Mont Blanc) : la quantité y est
 * le prix d'un panier, pas leur nombre.
 */
export function nombreDePaniersModifiable(saisie: {
  name: string;
  is_socially_taxed: boolean;
  sur_le_net?: boolean;
  quantity_kind?: 'count' | 'unit_value' | null;
}): boolean {
  return afficherBlocPanier(saisie.name, saisie) && saisie.quantity_kind !== 'unit_value';
}

/** « 15 », « 14,5 » : un nombre de paniers positif, ou null. */
export function lireNombreDePaniers(texte: string): number | null {
  const n = Number(texte.trim().replace(',', '.'));
  return Number.isFinite(n) && n > 0 ? n : null;
}

/** « 15 paniers », « 1 panier », « 14,5 paniers ». */
export function libelleNombreDePaniers(nombre: number | null | undefined): string {
  if (nombre == null) return 'Nombre de paniers ?';
  const texte = String(nombre).replace('.', ',');
  return `${texte} ${nombre > 1 ? 'paniers' : 'panier'}`;
}
