import type {
  RatesSyncCotisationUnit,
  RatesSyncRequest,
  RatesSyncSourcesManifest,
  RatesSyncSourceUnit,
} from '@/api/rates';
import { isLegisocialSourceUrl } from '@/lib/rateSourceLinks';

export type RatesSyncTarget =
  | { scope: 'all' }
  | { scope: 'rate_key'; rateKey: string }
  | { scope: 'rate_keys'; rateKeys: string[]; sectionLabel?: string }
  | { scope: 'source_key'; sourceKey: string }
  | { scope: 'cotisation_id'; cotisationId: string }
  | { scope: 'cotisation_bundle'; cotisationIds: string[] };

/** Clés payroll des paramètres clés (SMIC, PSS, IJ). */
export const KEY_PARAMS_RATE_KEYS = ['smic', 'pss', 'ij_plafonds'] as const;

const BAREMES_EXCLUDED_KEYS = new Set([
  'smic',
  'pss',
  'ij_plafonds',
  'cotisations',
]);

const BAREMES_ORDERED_KEYS = ['pas', 'frais_pro', 'avantages_en_nature', 'heures_supp', 'primes'] as const;

export function getBaremesRateKeysFromData(
  data: Record<string, { config_data?: unknown } | undefined>,
): string[] {
  const keys: string[] = [];
  for (const key of BAREMES_ORDERED_KEYS) {
    if (data[key]?.config_data) keys.push(key);
  }
  for (const key of Object.keys(data)) {
    if (!BAREMES_EXCLUDED_KEYS.has(key) && data[key]?.config_data) {
      keys.push(key);
    }
  }
  return keys;
}

export function syncTargetToRequest(target: RatesSyncTarget): RatesSyncRequest {
  switch (target.scope) {
    case 'all':
      return {};
    case 'rate_key':
      return { rate_keys: [target.rateKey] };
    case 'rate_keys':
      return { rate_keys: target.rateKeys };
    case 'source_key':
      return { source_keys: [target.sourceKey] };
    case 'cotisation_id':
      return { cotisation_ids: [target.cotisationId] };
    case 'cotisation_bundle':
      return { cotisation_ids: target.cotisationIds };
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

/** URLs officielles (manifest) + recoupement LegiSocial depuis source_links parent. */
export function buildSourceLinksForManifestSources(
  sources: RatesSyncSourceUnit[],
  categoryLinks?: string[] | null,
): string[] {
  const seen = new Set<string>();
  const links: string[] = [];
  let hasOfficialFromManifest = false;

  for (const src of sources) {
    const url = src.primary_url?.trim();
    if (url && !seen.has(url)) {
      seen.add(url);
      links.push(url);
      hasOfficialFromManifest = true;
    }
  }

  for (const raw of categoryLinks ?? []) {
    const url = raw?.trim();
    if (!url || seen.has(url)) continue;
    if (isLegisocialSourceUrl(url)) {
      seen.add(url);
      links.push(url);
      continue;
    }
    if (!hasOfficialFromManifest) {
      seen.add(url);
      links.push(url);
    }
  }

  return links;
}

export function sourceLinksForCotisationId(
  manifest: RatesSyncSourcesManifest | undefined,
  cotisationId: string,
  categoryLinks?: string[] | null,
): string[] {
  return buildSourceLinksForManifestSources(
    sourcesForCotisationId(manifest, cotisationId),
    categoryLinks,
  );
}

export function sourceLinksForRateKey(
  manifest: RatesSyncSourcesManifest | undefined,
  rateKey: string,
  categoryLinks?: string[] | null,
): string[] {
  return buildSourceLinksForManifestSources(
    sourcesForRateKey(manifest, rateKey),
    categoryLinks,
  );
}

/** Sources dédupliquées pour plusieurs rate_key (mise à jour d’une section entière). */
export function sourcesForRateKeys(
  manifest: RatesSyncSourcesManifest | undefined,
  rateKeys: string[],
): RatesSyncSourceUnit[] {
  const seen = new Set<string>();
  const result: RatesSyncSourceUnit[] = [];
  for (const rateKey of rateKeys) {
    for (const src of sourcesForRateKey(manifest, rateKey)) {
      const norm = src.source_key.trim().toUpperCase().replace(/-/g, '_');
      if (seen.has(norm)) continue;
      seen.add(norm);
      result.push(src);
    }
  }
  return result;
}

export function sourcesForCotisationId(
  manifest: RatesSyncSourcesManifest | undefined,
  cotisationId: string,
): RatesSyncSourceUnit[] {
  const cotisations = manifest?.rate_categories.find((c) => c.rate_key === 'cotisations');
  const units = cotisations?.cotisation_units ?? [];
  const exact = units.find((u) => u.cotisation_id === cotisationId);
  if (exact) return exact.sources;
  const norm = cotisationId.trim().toLowerCase();
  const byCase = units.find((u) => u.cotisation_id.trim().toLowerCase() === norm);
  return byCase?.sources ?? [];
}

export function sourceKeysForTarget(
  manifest: RatesSyncSourcesManifest | undefined,
  target: RatesSyncTarget,
): string[] {
  if (!manifest) return [];
  switch (target.scope) {
    case 'all': {
      const seen = new Set<string>();
      const keys: string[] = [];
      for (const cat of manifest.rate_categories) {
        for (const src of cat.sources) {
          const norm = src.source_key.trim().toUpperCase().replace(/-/g, '_');
          if (seen.has(norm)) continue;
          seen.add(norm);
          keys.push(src.source_key);
        }
      }
      return keys;
    }
    case 'rate_key':
      return sourcesForRateKey(manifest, target.rateKey).map((s) => s.source_key);
    case 'rate_keys':
      return sourcesForRateKeys(manifest, target.rateKeys).map((s) => s.source_key);
    case 'source_key':
      return [target.sourceKey];
    case 'cotisation_id':
      return sourcesForCotisationId(manifest, target.cotisationId).map((s) => s.source_key);
    case 'cotisation_bundle': {
      const seen = new Set<string>();
      const keys: string[] = [];
      for (const cid of target.cotisationIds) {
        for (const src of sourcesForCotisationId(manifest, cid)) {
          const norm = normalizeSourceKey(src.source_key);
          if (seen.has(norm)) continue;
          seen.add(norm);
          keys.push(src.source_key);
        }
      }
      return keys;
    }
    default:
      return [];
  }
}

export function findCotisationUnit(
  manifest: RatesSyncSourcesManifest | undefined,
  cotisationId: string,
): RatesSyncCotisationUnit | undefined {
  const units =
    manifest?.rate_categories.find((c) => c.rate_key === 'cotisations')?.cotisation_units ?? [];
  const exact = units.find((u) => u.cotisation_id === cotisationId);
  if (exact) return exact;
  const norm = cotisationId.trim().toLowerCase();
  return units.find((u) => u.cotisation_id.trim().toLowerCase() === norm);
}

/** Identifiants de lots de sync en cours (dédupliqués), pour reprise après rechargement. */
export function collectRunningSyncIdsFromManifest(
  manifest: RatesSyncSourcesManifest | undefined,
): string[] {
  if (!manifest) return [];
  const ids = new Set<string>();
  for (const cat of manifest.rate_categories) {
    for (const src of cat.sources) {
      if (src.is_running && src.sync_id) ids.add(src.sync_id);
    }
    for (const unit of cat.cotisation_units ?? []) {
      for (const src of unit.sources) {
        if (src.is_running && src.sync_id) ids.add(src.sync_id);
      }
    }
  }
  return [...ids];
}

export function manifestHasRunningSources(manifest: RatesSyncSourcesManifest | undefined): boolean {
  return collectRunningSyncIdsFromManifest(manifest).length > 0;
}

export function syncRequestToTarget(request?: RatesSyncRequest): RatesSyncTarget {
  if (!request) return { scope: 'all' };
  if (request.rate_keys?.length === 1) {
    return { scope: 'rate_key', rateKey: request.rate_keys[0] };
  }
  if (request.rate_keys && request.rate_keys.length > 1) {
    return { scope: 'rate_keys', rateKeys: request.rate_keys };
  }
  if (request.source_keys?.length === 1) {
    return { scope: 'source_key', sourceKey: request.source_keys[0] };
  }
  if (request.cotisation_ids?.length === 1) {
    return { scope: 'cotisation_id', cotisationId: request.cotisation_ids[0] };
  }
  if (request.cotisation_ids && request.cotisation_ids.length > 1) {
    return { scope: 'cotisation_bundle', cotisationIds: request.cotisation_ids };
  }
  return { scope: 'all' };
}

export function normalizeSourceKey(key: string): string {
  return key.trim().toUpperCase().replace(/-/g, '_');
}

/** Spinner carte barème / paramètre clé : uniquement si la sync active cible ce rate_key (ou tout). */
export function activeSyncCoversRateKey(
  active: RatesSyncTarget,
  rateKey: string,
): boolean {
  switch (active.scope) {
    case 'all':
      return true;
    case 'rate_key':
      return active.rateKey === rateKey;
    case 'rate_keys':
      return active.rateKeys.includes(rateKey);
    default:
      return false;
  }
}

/** Spinner menu source : uniquement si l’utilisateur a lancé une sync sur cette source. */
export function activeSyncCoversSourceKey(
  active: RatesSyncTarget,
  sourceKey: string,
): boolean {
  if (active.scope !== 'source_key') return false;
  return normalizeSourceKey(active.sourceKey) === normalizeSourceKey(sourceKey);
}

type SyncJobLike = {
  source_key: string;
  cotisation_ids?: string[];
  status: string;
};

/** True si la cible de sync concerne explicitement cette ligne (pas les sœurs même source). */
export function cotisationMatchesSyncTarget(
  manifest: RatesSyncSourcesManifest | undefined,
  target: RatesSyncTarget,
  cotisationId: string,
): boolean {
  const norm = cotisationId.trim().toLowerCase();
  switch (target.scope) {
    case 'cotisation_id':
      return target.cotisationId.trim().toLowerCase() === norm;
    case 'cotisation_bundle':
      return target.cotisationIds.some((id) => id.trim().toLowerCase() === norm);
    case 'source_key':
      return sourcesForCotisationId(manifest, cotisationId).some(
        (s) => normalizeSourceKey(s.source_key) === normalizeSourceKey(target.sourceKey),
      );
    case 'all':
      return true;
    case 'rate_key':
    case 'rate_keys':
      return false;
    default:
      return false;
  }
}

const TERMINAL_JOB_STATUSES = new Set(['completed', 'failed', 'cancelled']);

/** True si un job en cours cible cette ligne (filtre cotisation_ids prioritaire). */
export function isActiveJobForCotisation(
  manifest: RatesSyncSourcesManifest | undefined,
  job: SyncJobLike,
  cotisationId: string,
): boolean {
  if (TERMINAL_JOB_STATUSES.has(job.status)) return false;
  const norm = cotisationId.trim().toLowerCase();
  const ids = job.cotisation_ids ?? [];
  if (ids.length > 0) {
    return ids.some((id) => id.trim().toLowerCase() === norm);
  }
  const lineSources = sourcesForCotisationId(manifest, cotisationId).map((s) =>
    normalizeSourceKey(s.source_key),
  );
  return lineSources.includes(normalizeSourceKey(job.source_key));
}

/** Spinner ligne : cible explicite ou job actif pour cette cotisation uniquement. */
export function isCotisationRunningInSync(
  manifest: RatesSyncSourcesManifest | undefined,
  params: { target: RatesSyncTarget; jobs?: SyncJobLike[] },
  cotisationId: string,
): boolean {
  const jobs = params.jobs ?? [];
  const activeJobs = jobs.filter((j) => !TERMINAL_JOB_STATUSES.has(j.status));
  const hasScopedJobs = activeJobs.some((j) => (j.cotisation_ids?.length ?? 0) > 0);

  if (hasScopedJobs) {
    return activeJobs.some((job) =>
      isActiveJobForCotisation(manifest, job, cotisationId),
    );
  }

  if (params.target.scope === 'cotisation_id' || params.target.scope === 'cotisation_bundle') {
    return cotisationMatchesSyncTarget(manifest, params.target, cotisationId);
  }

  if (cotisationMatchesSyncTarget(manifest, params.target, cotisationId)) return true;
  return activeJobs.some((job) =>
    isActiveJobForCotisation(manifest, job, cotisationId),
  );
}
