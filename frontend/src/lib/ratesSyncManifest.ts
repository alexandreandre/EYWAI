import type {
  RatesSyncCotisationUnit,
  RatesSyncRequest,
  RatesSyncSourcesManifest,
  RatesSyncSourceUnit,
} from '@/api/rates';

export type RatesSyncTarget =
  | { scope: 'all' }
  | { scope: 'rate_key'; rateKey: string }
  | { scope: 'source_key'; sourceKey: string }
  | { scope: 'cotisation_id'; cotisationId: string };

export function syncTargetToRequest(target: RatesSyncTarget): RatesSyncRequest {
  switch (target.scope) {
    case 'all':
      return {};
    case 'rate_key':
      return { rate_keys: [target.rateKey] };
    case 'source_key':
      return { source_keys: [target.sourceKey] };
    case 'cotisation_id':
      return { cotisation_ids: [target.cotisationId] };
    default:
      return {};
  }
}

export function sourcesForRateKey(
  manifest: RatesSyncSourcesManifest | undefined,
  rateKey: string,
): RatesSyncSourceUnit[] {
  return manifest?.rate_categories.find((c) => c.rate_key === rateKey)?.sources ?? [];
}

export function sourcesForCotisationId(
  manifest: RatesSyncSourcesManifest | undefined,
  cotisationId: string,
): RatesSyncSourceUnit[] {
  const cotisations = manifest?.rate_categories.find((c) => c.rate_key === 'cotisations');
  return (
    cotisations?.cotisation_units?.find((u) => u.cotisation_id === cotisationId)?.sources ?? []
  );
}

export function sourceKeysForTarget(
  manifest: RatesSyncSourcesManifest | undefined,
  target: RatesSyncTarget,
): string[] {
  if (!manifest) return [];
  switch (target.scope) {
    case 'all':
      return manifest.rate_categories.flatMap((c) => c.sources.map((s) => s.source_key));
    case 'rate_key':
      return sourcesForRateKey(manifest, target.rateKey).map((s) => s.source_key);
    case 'source_key':
      return [target.sourceKey];
    case 'cotisation_id':
      return sourcesForCotisationId(manifest, target.cotisationId).map((s) => s.source_key);
    default:
      return [];
  }
}

export function findCotisationUnit(
  manifest: RatesSyncSourcesManifest | undefined,
  cotisationId: string,
): RatesSyncCotisationUnit | undefined {
  return manifest?.rate_categories
    .find((c) => c.rate_key === 'cotisations')
    ?.cotisation_units?.find((u) => u.cotisation_id === cotisationId);
}
