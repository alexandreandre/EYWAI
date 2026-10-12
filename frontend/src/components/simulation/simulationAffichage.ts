/**
 * Mise en forme des montants et des taux de la page « Simulation de Paie ».
 * Format français : virgule décimale, espace des milliers, espace avant « % »,
 * signe moins typographique (−).
 */

const FORMAT_EUROS = new Intl.NumberFormat('fr-FR', {
  style: 'currency',
  currency: 'EUR',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const FORMAT_POURCENT = new Intl.NumberFormat('fr-FR', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 3,
});

function nombre(valeur: unknown): number | null {
  if (valeur === null || valeur === undefined || valeur === '') return null;
  const n = Number(valeur);
  return Number.isFinite(n) ? n : null;
}

/** « 2 450,00 € », « −0,32 € » ; « — » sans valeur. */
export function euros(valeur: unknown): string {
  const n = nombre(valeur);
  if (n === null) return '—';
  const arrondi = Math.abs(n) < 0.005 ? 0 : n;
  return FORMAT_EUROS.format(arrondi).replace('-', '−');
}

/** Un montant retenu, toujours précédé du signe moins : « −268,28 € ». */
export function eurosRetenus(valeur: unknown): string {
  const n = nombre(valeur);
  if (n === null) return '—';
  return euros(-Math.abs(n));
}

/** Un taux stocké en fraction (0,0315) affiché en pourcentage : « 3,15 % ». */
export function tauxEnPourcent(taux: unknown): string {
  const n = nombre(taux);
  if (n === null) return '—';
  return `${FORMAT_POURCENT.format(n * 100)}\u00a0%`;
}

/** Un taux déjà en pourcentage (2,1 pour 2,1 %) : « 2,1 % ». */
export function pourcent(valeur: unknown, decimales = 1): string {
  const n = nombre(valeur);
  if (n === null) return '—';
  return `${n.toFixed(decimales).replace('.', ',')}\u00a0%`;
}

type LigneBrute = {
  libelle?: string;
  base?: unknown;
  taux_salarial?: unknown;
  montant_salarial?: unknown;
  taux_patronal?: unknown;
  montant_patronal?: unknown;
};

export type LigneDetailCotisation = {
  libelle: string;
  base: string;
  tauxSalarial: string;
  partSalariale: string;
  tauxPatronal: string;
  partPatronale: string;
};

/** Taux et part d'un côté : « — » pour les deux quand ce côté ne cotise pas. */
function cote(taux: unknown, montant: unknown): [string, string] {
  const t = nombre(taux);
  const m = nombre(montant) ?? 0;
  if (Math.abs(m) < 0.005 && (t === null || t === 0)) return ['—', '—'];
  return [t === null ? '—' : tauxEnPourcent(t), euros(m)];
}

/**
 * Les lignes du « Détail des cotisations » : cotisations principales,
 * allègements (réduction générale), CSG et CRDS, puis contributions
 * patronales. Les taux du moteur sont des fractions (0,0315), les parts sont
 * `montant_salarial` et `montant_patronal`.
 */
export function lignesDetailCotisations(structure: unknown): LigneDetailCotisation[] {
  if (!structure || typeof structure !== 'object') return [];
  const s = structure as Record<string, unknown>;
  const autres = s.bloc_autres_contributions as { lignes?: unknown } | undefined;
  const blocs = [s.bloc_principales, s.bloc_allegements, s.bloc_csg_non_deductible, autres?.lignes];
  const lignes: LigneBrute[] = blocs.flatMap((b) => (Array.isArray(b) ? b : []));
  return lignes.map((l) => {
    const [tauxSalarial, partSalariale] = cote(l.taux_salarial, l.montant_salarial);
    const [tauxPatronal, partPatronale] = cote(l.taux_patronal, l.montant_patronal);
    return {
      libelle: String(l.libelle ?? ''),
      base: euros(l.base),
      tauxSalarial,
      partSalariale,
      tauxPatronal,
      partPatronale,
    };
  });
}

const MOIS = [
  'janvier',
  'février',
  'mars',
  'avril',
  'mai',
  'juin',
  'juillet',
  'août',
  'septembre',
  'octobre',
  'novembre',
  'décembre',
];

type HypothesesCalculInverse = {
  month?: number;
  year?: number;
  type_contrat?: string;
  type_contrat_par_defaut?: boolean;
};

/**
 * Ce sur quoi le calcul inverse a compté : « Calcul sur octobre 2026, pour un
 * CDI (type de contrat retenu par défaut). » ; null sans période.
 */
export function phraseCalculInverse(resultat: HypothesesCalculInverse): string | null {
  const { month, year, type_contrat: contrat, type_contrat_par_defaut: parDefaut } = resultat;
  if (!month || !year || !MOIS[month - 1]) return null;
  const periode = `Calcul sur ${MOIS[month - 1]} ${year}`;
  if (!contrat) return `${periode}.`;
  const pourQui = ['CDI', 'CDD'].includes(contrat.toUpperCase())
    ? `pour un ${contrat.toUpperCase()}`
    : `pour le contrat « ${contrat} »`;
  return `${periode}, ${pourQui}${parDefaut ? ' (type de contrat retenu par défaut)' : ''}.`;
}
