import type { RatesSyncSourcesManifest } from '@/api/rates';
import {
  normalizeSourceKey,
  sourcesForCotisationId,
} from '@/lib/ratesSyncManifest';
import type { Cotisation } from '@/lib/ratesUtils';

export type CotisationDisplayBundle = {
  type: 'bundle';
  bundleKey: string;
  sourceName: string;
  cotisations: Cotisation[];
  cotisationIds: string[];
  /** Lot mono-source (ex. AGIRC) : sync via source_key */
  sourceKey?: string;
};

export type CotisationDisplayRow =
  | { type: 'single'; cotisation: Cotisation }
  | CotisationDisplayBundle;

/** Lots multi-lignes sans source unique partagée (sync groupée par cotisation_ids). */
const EXPLICIT_COTISATION_BUNDLES: ReadonlyArray<{
  key: string;
  label: string;
  memberIds: readonly string[];
}> = [
  {
    key: 'securite_sociale_mmid_vieillesse',
    label: 'Sécurité sociale — maladie & vieillesse',
    memberIds: [
      'securite_sociale_maladie',
      'retraite_secu_plafond',
      'retraite_secu_deplafond',
    ],
  },
];

/** Ordre d’affichage des lignes dans un lot connu (aligné scraping). */
const BUNDLE_MEMBER_ORDER: Record<string, readonly string[]> = {
  AGIRC_ARRCO: [
    'retraite_comp_t1',
    'retraite_comp_t2',
    'ceg_t1',
    'ceg_t2',
    'cet',
    'apec',
  ],
  TAXE_APPRENTISSAGE: ['taxe_apprentissage', 'taxe_apprentissage_solde'],
  securite_sociale_mmid_vieillesse: [
    'securite_sociale_maladie',
    'retraite_secu_plafond',
    'retraite_secu_deplafond',
  ],
};

const BUNDLE_LABELS: Record<string, string> = {
  AGIRC_ARRCO: 'AGIRC ARRCO',
  TAXE_APPRENTISSAGE: 'Taxe d’apprentissage',
  securite_sociale_mmid_vieillesse: 'Sécurité sociale — maladie & vieillesse',
};

function normCotisationId(id: string): string {
  return id.trim().toLowerCase();
}

function sortCotisationsInBundle(
  orderKey: string,
  items: Cotisation[],
): Cotisation[] {
  const order = BUNDLE_MEMBER_ORDER[orderKey];
  if (!order) {
    return [...items].sort((a, b) => a.libelle.localeCompare(b.libelle, 'fr'));
  }
  const rank = new Map(order.map((id, i) => [normCotisationId(id), i]));
  return [...items].sort((a, b) => {
    const ra = rank.get(normCotisationId(a.id)) ?? 999;
    const rb = rank.get(normCotisationId(b.id)) ?? 999;
    if (ra !== rb) return ra - rb;
    return a.libelle.localeCompare(b.libelle, 'fr');
  });
}

export function bundleDisplayLabel(orderKey: string, fallbackName: string): string {
  return BUNDLE_LABELS[orderKey] ?? fallbackName;
}

function collectExplicitBundles(
  byId: Map<string, Cotisation>,
  consumed: Set<string>,
): CotisationDisplayBundle[] {
  const rows: CotisationDisplayBundle[] = [];

  for (const def of EXPLICIT_COTISATION_BUNDLES) {
    const members = def.memberIds
      .map((id) => byId.get(normCotisationId(id)))
      .filter((c): c is Cotisation => Boolean(c));

    if (members.length < 2) continue;

    for (const c of members) {
      consumed.add(normCotisationId(c.id));
    }

    rows.push({
      type: 'bundle',
      bundleKey: def.key,
      sourceName: def.label,
      cotisations: sortCotisationsInBundle(def.key, members),
      cotisationIds: members.map((c) => c.id),
    });
  }

  return rows;
}

/**
 * Regroupe les cotisations : lots explicites, puis source scraping unique partagée.
 */
export function buildCotisationDisplayRows(
  manifest: RatesSyncSourcesManifest | undefined,
  cotisations: Cotisation[],
): CotisationDisplayRow[] {
  const byId = new Map(cotisations.map((c) => [normCotisationId(c.id), c]));
  const consumed = new Set<string>();
  const rows: CotisationDisplayRow[] = [];

  rows.push(...collectExplicitBundles(byId, consumed));

  const remaining = cotisations.filter((c) => !consumed.has(normCotisationId(c.id)));
  const bySingleSource = new Map<string, { sourceKey: string; sourceName: string; items: Cotisation[] }>();
  const singles: Cotisation[] = [];

  for (const coti of remaining) {
    const sources = sourcesForCotisationId(manifest, coti.id);
    const uniqueNorm = [...new Set(sources.map((s) => normalizeSourceKey(s.source_key)))];

    if (uniqueNorm.length === 1 && sources.length > 0) {
      const norm = uniqueNorm[0];
      const bucket = bySingleSource.get(norm) ?? {
        sourceKey: sources[0].source_key,
        sourceName: sources[0].source_name,
        items: [],
      };
      bucket.items.push(coti);
      bySingleSource.set(norm, bucket);
    } else {
      singles.push(coti);
    }
  }

  for (const [norm, bucket] of bySingleSource) {
    if (bucket.items.length > 1) {
      const sorted = sortCotisationsInBundle(norm, bucket.items);
      rows.push({
        type: 'bundle',
        bundleKey: `source:${norm}`,
        sourceKey: bucket.sourceKey,
        sourceName: bundleDisplayLabel(norm, bucket.sourceName),
        cotisations: sorted,
        cotisationIds: sorted.map((c) => c.id),
      });
    } else if (bucket.items.length === 1) {
      singles.push(bucket.items[0]);
    }
  }

  for (const coti of singles) {
    rows.push({ type: 'single', cotisation: coti });
  }

  const rowLabel = (row: CotisationDisplayRow): string =>
    row.type === 'bundle' ? row.sourceName : (row.cotisation.libelle ?? '');

  return rows.sort((a, b) => rowLabel(a).localeCompare(rowLabel(b), 'fr'));
}

function cotisationSearchText(c: Cotisation): string {
  return [c.libelle, c.base, c.id].filter(Boolean).join(' ').toLowerCase();
}

export function rowMatchesSearch(row: CotisationDisplayRow, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  if (row.type === 'bundle' && row.sourceName.toLowerCase().includes(q)) return true;
  const cotis = row.type === 'bundle' ? row.cotisations : [row.cotisation];
  return cotis.some((c) => cotisationSearchText(c).includes(q));
}

export function bundleSourceNorm(sourceKey: string): string {
  return normalizeSourceKey(sourceKey);
}
