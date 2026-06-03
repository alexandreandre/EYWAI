import type { RatesSyncJob, RatesSyncStatusResponse } from '@/api/rates';
import type { RatesSyncTarget } from '@/lib/ratesSyncManifest';

const STORAGE_KEY = 'eywai_rates_sync_durations_v1';

type StoredEntry = {
  durationSec: number;
  updatedAt: string;
};

type DurationStore = Record<string, StoredEntry>;

function readStore(): DurationStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (!parsed || typeof parsed !== 'object') return {};
    return parsed as DurationStore;
  } catch {
    return {};
  }
}

function writeStore(store: DurationStore): void {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(store));
  } catch {
    // quota / mode privé — ignoré
  }
}

/** Clés de persistance pour une cible de sync (rate_key, section, cotisation…). */
export function storageKeysFromTarget(target: RatesSyncTarget): string[] {
  switch (target.scope) {
    case 'rate_key':
      return [target.rateKey];
    case 'rate_keys':
      return [...target.rateKeys];
    case 'all':
      return ['__all__'];
    case 'source_key':
      return [`source:${target.sourceKey}`];
    case 'cotisation_id':
      return [`cotisation:${target.cotisationId}`];
    case 'cotisation_bundle':
      return target.cotisationIds.map((id) => `cotisation:${id}`);
    default:
      return [];
  }
}

export function getStoredSyncDuration(storageKey: string): number | null {
  const entry = readStore()[storageKey];
  if (!entry || typeof entry.durationSec !== 'number' || entry.durationSec <= 0) {
    return null;
  }
  return entry.durationSec;
}

/** Somme des durées connues pour plusieurs clés (ex. section « Paramètres clés »). */
export function sumStoredSyncDurationForKeys(keys: string[]): number | null {
  const unique = [...new Set(keys.filter(Boolean))];
  let total = 0;
  let found = false;
  for (const key of unique) {
    const stored = getStoredSyncDuration(key);
    if (stored != null) {
      total += stored;
      found = true;
    }
  }
  return found ? total : null;
}

export function sumStoredSyncDurationForFullSync(): number | null {
  const storedAll = getStoredSyncDuration('__all__');
  if (storedAll != null) return storedAll;

  return maxStoredSyncDurationFromStore();
}

/** Durée murale estimée (jobs parallèles) : max des durées connues par source / rate_key. */
export function maxStoredSyncDurationFromStore(): number | null {
  const store = readStore();
  let maxSec = 0;
  let found = false;

  for (const [key, entry] of Object.entries(store)) {
    if (!entry?.durationSec || entry.durationSec <= 0) continue;
    if (key.startsWith('cotisation:')) continue;
    if (key === '__all__') continue;
    maxSec = Math.max(maxSec, entry.durationSec);
    found = true;
  }

  return found ? maxSec : null;
}

export const DEFAULT_SYNC_JOB_DURATION_SEC = 90;

/** Durée attendue d'un job (historique local source → rate_key → défaut). */
export function getJobExpectedDurationSec(job: RatesSyncJob): number {
  const sourceKey = job.source_key?.trim();
  if (sourceKey) {
    const fromSource = getStoredSyncDuration(`source:${sourceKey}`);
    if (fromSource != null) return fromSource;
  }

  const rateKeys = (job.rate_keys ?? []).filter(Boolean);
  if (rateKeys.length > 0) {
    const fromRates = sumStoredSyncDurationForKeys(rateKeys);
    if (fromRates != null) return fromRates;
  }

  return DEFAULT_SYNC_JOB_DURATION_SEC;
}

export function sumExpectedDurationForJobs(jobs: RatesSyncJob[]): number {
  if (jobs.length === 0) return 0;
  return jobs.reduce((sum, job) => sum + getJobExpectedDurationSec(job), 0);
}

export function sumStoredSyncDurationForTarget(target: RatesSyncTarget): number | null {
  if (target.scope === 'all') {
    return sumStoredSyncDurationForFullSync();
  }
  return sumStoredSyncDurationForKeys(storageKeysFromTarget(target));
}

export function recordSyncDurationForKeys(keys: string[], durationSec: number): void {
  const unique = [...new Set(keys.filter(Boolean))];
  if (unique.length === 0 || durationSec <= 0) return;

  const store = readStore();
  const updatedAt = new Date().toISOString();
  const rounded = Math.max(1, Math.round(durationSec));

  for (const key of unique) {
    store[key] = { durationSec: rounded, updatedAt };
  }
  writeStore(store);
}

/** Durée murale d’un lot terminé (created_at → dernière fin de job). */
export function computeCompletedSyncDurationSec(status: RatesSyncStatusResponse): number {
  const startMs = status.created_at ? Date.parse(status.created_at) : NaN;
  if (!Number.isFinite(startMs)) return 0;

  const completedMs = status.jobs
    .map((job) => (job.completed_at ? Date.parse(job.completed_at) : 0))
    .filter((t) => t > 0);

  const endMs =
    completedMs.length > 0 && completedMs.length === status.jobs.length
      ? Math.max(...completedMs)
      : Date.now();

  return Math.max(1, Math.round((endMs - startMs) / 1000));
}

/** Durée d’un job individuel (source / carte). */
export function computeJobDurationSec(
  job: RatesSyncJob,
  batchStartMs: number,
): number {
  const startMs = job.started_at ? Date.parse(job.started_at) : batchStartMs;
  const endMs = job.completed_at ? Date.parse(job.completed_at) : Date.now();
  if (!Number.isFinite(startMs) || !Number.isFinite(endMs)) return 0;
  return Math.max(1, Math.round((endMs - startMs) / 1000));
}

function storageKeysFromJob(job: RatesSyncJob): string[] {
  const keys: string[] = [];
  for (const rateKey of job.rate_keys ?? []) {
    if (rateKey) keys.push(rateKey);
  }
  for (const cotisationId of job.cotisation_ids ?? []) {
    if (cotisationId) keys.push(`cotisation:${cotisationId}`);
  }
  if (keys.length === 0 && job.source_key) {
    keys.push(`source:${job.source_key}`);
  }
  return keys;
}

export function recordSyncDurationFromStatus(
  target: RatesSyncTarget,
  status: RatesSyncStatusResponse,
): void {
  if (status.status === 'cancelled') return;

  const batchStartMs = status.created_at ? Date.parse(status.created_at) : NaN;
  const jobs = status.jobs ?? [];

  if (jobs.length > 0) {
    for (const job of jobs) {
      if (job.status === 'cancelled') continue;
      const keys = storageKeysFromJob(job);
      if (keys.length === 0) continue;
      const durationSec = computeJobDurationSec(job, batchStartMs);
      if (durationSec <= 0) continue;
      recordSyncDurationForKeys(keys, durationSec);
    }
    if (target.scope === 'all') {
      const wallSec = computeCompletedSyncDurationSec(status);
      if (wallSec > 0) {
        recordSyncDurationForKeys(['__all__'], wallSec);
      }
    }
    return;
  }

  const durationSec = computeCompletedSyncDurationSec(status);
  if (durationSec <= 0) return;

  recordSyncDurationForKeys(storageKeysFromTarget(target), durationSec);
}
