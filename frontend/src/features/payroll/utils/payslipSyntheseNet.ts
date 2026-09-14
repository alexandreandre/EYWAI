/**
 * Recalculs dérivés de l'écran d'édition d'un bulletin, faits **au moment
 * où la RH modifie un champ** et jamais au chargement.
 *
 * Deux sections recalculaient dans un `useEffect` au montage : la synthèse
 * net refaisait « net social − impôt + transport » et les cotisations
 * resommaient leurs blocs. Le résultat repassait par `onChange`, c'est-à-dire
 * par le même chemin qu'une saisie de la RH, avec deux effets :
 * - le bruit flottant (2973,61 − 65,66 = 2907,9500000000003 en JavaScript)
 *   marquait le bulletin « modifié » dès l'ouverture, barre d'enregistrement
 *   comprise (audit du 13/09/2026, Bugny juillet) ;
 * - la formule de l'écran ignore ce que le moteur retire ou ajoute au net
 *   (titres-restaurant, acompte, primes non soumises, participation) : sur les
 *   bulletins Zone 404 avec abonnement transport, ouvrir l'éditeur réécrivait
 *   un net à payer faux de +36,50 €, prêt à être enregistré.
 *
 * Ici, le net enregistré reste la référence : une modification le décale
 * seulement de la différence saisie, avec le signe du champ.
 */

const ARRONDI = (valeur: number): number => Math.round(valeur * 100) / 100;

/** Effet d'un champ de la synthèse sur le net à payer : +1, −1 ou aucun. */
const SIGNE_SUR_LE_NET: Record<string, 1 | -1> = {
  net_social_avant_impot: 1,
  'impot_prelevement_a_la_source.montant': -1,
  remboursement_transport: 1,
  indemnite_transport_fixe: 1,
};

const nombre = (valeur: unknown): number => {
  const n = typeof valeur === 'number' ? valeur : parseFloat(String(valeur ?? ''));
  return Number.isFinite(n) ? n : 0;
};

/**
 * Net à payer après qu'un champ de la synthèse a été modifié à la main.
 * Les champs sans effet direct (net imposable, base et taux de l'impôt)
 * laissent le net tel quel.
 */
export function netAPayerApresModification(
  netActuel: unknown,
  champ: string,
  ancienneValeur: unknown,
  nouvelleValeur: unknown
): number {
  const signe = SIGNE_SUR_LE_NET[champ];
  const net = nombre(netActuel);
  if (!signe) return ARRONDI(net);
  return ARRONDI(net + signe * (nombre(nouvelleValeur) - nombre(ancienneValeur)));
}

const BLOCS_COTISATIONS = ['bloc_principales', 'bloc_allegements', 'bloc_csg_non_deductible'] as const;

/** Totaux salarial et patronal des trois blocs, arrondis au centime. */
export function totauxCotisations(structure: unknown): {
  total_salarial: number;
  total_patronal: number;
} {
  let salarial = 0;
  let patronal = 0;
  const data = (structure && typeof structure === 'object' ? structure : {}) as Record<
    string,
    unknown
  >;
  for (const bloc of BLOCS_COTISATIONS) {
    const lignes = Array.isArray(data[bloc]) ? (data[bloc] as unknown[]) : [];
    for (const ligne of lignes) {
      if (!ligne || typeof ligne !== 'object') continue;
      const { montant_salarial, montant_patronal } = ligne as Record<string, unknown>;
      salarial += nombre(montant_salarial);
      patronal += nombre(montant_patronal);
    }
  }
  return { total_salarial: ARRONDI(salarial), total_patronal: ARRONDI(patronal) };
}

/** Structure de cotisations dont les totaux suivent les lignes. */
export function avecTotauxCotisations<T extends Record<string, unknown>>(
  structure: T
): T & { total_salarial: number; total_patronal: number } {
  return { ...structure, ...totauxCotisations(structure) };
}
