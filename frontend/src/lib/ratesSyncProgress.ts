import type { RatesSyncJob, RatesSyncStatusResponse } from '@/api/rates';
import { getCategoryTitle, getCotisationTitle } from '@/lib/ratesLabels';
import {
  DEFAULT_SYNC_JOB_DURATION_SEC,
  getJobExpectedDurationSec,
  maxStoredSyncDurationFromStore,
} from '@/lib/ratesSyncDurationStorage';
import type { RatesSyncTarget } from '@/lib/ratesSyncManifest';

/**
 * Libellé RH pour une durée mesurée (secondes ou minutes).
 */
export function formatSyncDuration(seconds: number | null | undefined): string | null {
  if (seconds == null || seconds <= 0) return null;

  const total = Math.max(1, Math.round(seconds));
  if (total < 60) return `${total} s`;

  const minutes = Math.floor(total / 60);
  const rem = total % 60;
  if (rem === 0) return minutes === 1 ? '1 min' : `${minutes} min`;
  if (minutes === 0) return `${total} s`;
  return `${minutes} min ${rem} s`;
}

/**
 * Temps écoulé depuis le début du lot le plus ancien encore actif.
 */
export function computeActiveSyncElapsedSec(
  statuses: Array<{ created_at?: string } | null | undefined>,
): number {
  let earliestMs: number | null = null;

  for (const status of statuses) {
    if (!status?.created_at) continue;
    const ms = Date.parse(status.created_at);
    if (!Number.isFinite(ms)) continue;
    earliestMs = earliestMs == null ? ms : Math.min(earliestMs, ms);
  }

  if (earliestMs == null) return 0;
  return Math.max(0, Math.round((Date.now() - earliestMs) / 1000));
}

/**
 * Estimation bandeau à partir des jobs (durée attendue par source, exécution parallèle).
 */
export function formatSyncProgressEstimateFromJobs(
  jobs: RatesSyncJob[],
  elapsedSec: number,
): string | null {
  const timing = computeSyncProgressFromJobs(jobs);
  if (timing.remainingSec != null && timing.remainingSec > 0) {
    const rem = formatSyncDuration(timing.remainingSec);
    return rem ? `Environ ${rem} restantes` : null;
  }
  if (timing.allDone) return 'Finalisation…';
  if (timing.wallEstimateSec != null && elapsedSec < 2) {
    const total = formatSyncDuration(timing.wallEstimateSec);
    return total ? `Environ ${total} restantes` : null;
  }
  return null;
}

/**
 * Progression pondérée par job + ETA (jobs lancés en parallèle → ETA = max des restants).
 */
export function computeSyncProgressFromJobs(jobs: RatesSyncJob[]): {
  percent: number;
  remainingSec: number | null;
  wallEstimateSec: number | null;
  allDone: boolean;
} {
  if (jobs.length === 0) {
    const fallback = maxStoredSyncDurationFromStore();
    return {
      percent: 8,
      remainingSec: fallback,
      wallEstimateSec: fallback,
      allDone: false,
    };
  }

  let weightedDone = 0;
  let totalWeight = 0;
  let maxRemaining = 0;
  let wallEstimateSec = 0;
  let incomplete = 0;

  for (const job of jobs) {
    const expected = getJobExpectedDurationSec(job);
    totalWeight += expected;
    wallEstimateSec = Math.max(wallEstimateSec, expected);

    const status = job.status;
    const terminal =
      status === 'completed' || status === 'failed' || status === 'cancelled';

    let frac = 0;
    if (terminal) {
      frac = 1;
    } else if (status === 'running') {
      frac = Math.min(0.99, Math.max(0, job.progress_fraction ?? 0));
      incomplete += 1;
      maxRemaining = Math.max(maxRemaining, (1 - frac) * expected);
    } else {
      incomplete += 1;
      maxRemaining = Math.max(maxRemaining, expected);
    }

    weightedDone += frac * expected;
  }

  const allDone = incomplete === 0;
  const percentExact = totalWeight > 0 ? (weightedDone / totalWeight) * 100 : 0;
  const percent = allDone
    ? 100
    : Math.min(99, Math.max(8, Math.round(percentExact)));

  return {
    percent,
    remainingSec: allDone || maxRemaining <= 3 ? null : Math.round(maxRemaining),
    wallEstimateSec: wallEstimateSec > 0 ? wallEstimateSec : DEFAULT_SYNC_JOB_DURATION_SEC,
    allDone,
  };
}

/** @deprecated Préférer formatSyncProgressEstimateFromJobs quand la liste des jobs est disponible */
export function formatSyncProgressEstimate(
  elapsedSec: number,
  referenceSec: number | null | undefined,
): string | null {
  if (referenceSec == null || referenceSec <= 0) {
    return null;
  }

  const ref = Math.max(1, Math.round(referenceSec));
  const elapsed = Math.max(0, Math.round(elapsedSec));
  const remaining = Math.max(0, ref - elapsed);

  if (elapsed < 2) {
    const total = formatSyncDuration(ref);
    return total ? `Environ ${total} restantes` : null;
  }

  if (remaining <= 0) {
    return 'Finalisation…';
  }

  const rem = formatSyncDuration(remaining);
  return rem ? `Environ ${rem} restantes` : null;
}

/** @deprecated Utiliser formatSyncProgressEstimate */
export const formatSyncProgressDuration = formatSyncProgressEstimate;

type SyncStatusLike = RatesSyncStatusResponse | null | undefined;

function jobFraction(job: RatesSyncJob): number {
  if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
    return 1;
  }
  if (job.status === 'running') {
    return Math.min(0.99, Math.max(0, job.progress_fraction ?? 0));
  }
  return 0;
}

export type AggregatedSyncProgress = {
  /** Pourcentage fidèle (0..100), pondéré par source et par progression réelle des jobs en cours */
  percent: number;
  totalJobs: number;
  doneJobs: number;
  runningJobs: number;
  pendingJobs: number;
  failedJobs: number;
  etaSeconds: number | null;
};

/** Agrège la progression de toutes les synchronisations actives en une seule vue. */
export function aggregateSyncProgress(statuses: SyncStatusLike[]): AggregatedSyncProgress {
  let totalJobs = 0;
  let fractionSum = 0;
  let doneJobs = 0;
  let runningJobs = 0;
  let pendingJobs = 0;
  let failedJobs = 0;
  let etaSeconds: number | null = null;

  for (const status of statuses) {
    if (!status) continue;
    const jobs = status.jobs ?? [];

    if (jobs.length > 0) {
      for (const job of jobs) {
        totalJobs += 1;
        fractionSum += jobFraction(job);
        if (job.status === 'failed' || job.success === false) {
          doneJobs += 1;
          failedJobs += 1;
        } else if (job.status === 'completed' || job.status === 'cancelled') {
          doneJobs += 1;
        } else if (job.status === 'running') {
          runningJobs += 1;
        } else {
          pendingJobs += 1;
        }
      }
    } else if (status.progress) {
      const total = status.progress.total || 0;
      const pct = (status.progress.percent_exact ?? status.progress.percent ?? 0) / 100;
      totalJobs += total;
      fractionSum += pct * total;
      doneJobs += status.progress.done ?? 0;
      runningJobs += status.progress.running ?? 0;
      pendingJobs += status.progress.pending ?? 0;
      failedJobs += status.progress.failed ?? 0;
    }

    const eta = status.progress?.eta_seconds;
    if (eta != null && eta > 0) {
      etaSeconds = etaSeconds == null ? eta : Math.max(etaSeconds, eta);
    }
  }

  const percent = totalJobs > 0 ? Math.min(100, Math.round((fractionSum / totalJobs) * 100)) : 0;

  return { percent, totalJobs, doneJobs, runningJobs, pendingJobs, failedJobs, etaSeconds };
}

/** Plafond temps avant fin réelle des jobs (évite un saut 0→100 à la dernière seconde). */
export const SYNC_PROGRESS_TIME_CAP = 92;

/**
 * Progression linéaire selon le temps écoulé / durée de référence (repli sans liste de jobs).
 */
export function computeTimeBasedSyncPercent(
  elapsedSec: number,
  referenceSec: number,
  options?: { allJobsDone?: boolean },
): number {
  if (options?.allJobsDone) return 100;

  const ref = Math.max(1, Math.round(referenceSec));
  const elapsed = Math.max(0, Math.round(elapsedSec));
  const ratio = elapsed / ref;
  const pct = Math.min(SYNC_PROGRESS_TIME_CAP, ratio * SYNC_PROGRESS_TIME_CAP);
  return Math.max(8, Math.round(pct));
}

export type SyncProgressTiming = {
  elapsedSec: number;
  /** @deprecated Préférer jobs + computeSyncProgressFromJobs */
  referenceSec?: number | null | undefined;
  awaitingStatus?: boolean;
  jobs?: RatesSyncJob[];
};

/**
 * Progression affichée : pondération par job (fraction serveur × durée attendue par source).
 */
export function displaySyncProgressPercent(
  agg: AggregatedSyncProgress,
  isActive: boolean,
  timing?: SyncProgressTiming,
): number {
  if (!isActive) return agg.percent;

  if (timing?.awaitingStatus) return 8;

  const jobs = timing?.jobs ?? [];
  if (jobs.length > 0) {
    const fromJobs = computeSyncProgressFromJobs(jobs);
    if (fromJobs.allDone) return 100;
    const serverPct = agg.totalJobs > 0 ? agg.percent : fromJobs.percent;
    return Math.min(99, Math.max(fromJobs.percent, serverPct));
  }

  const ref = timing?.referenceSec;
  if (ref != null && ref > 0 && !timing?.awaitingStatus) {
    const allJobsDone =
      agg.totalJobs > 0 && agg.doneJobs >= agg.totalJobs && agg.runningJobs === 0;
    return computeTimeBasedSyncPercent(timing.elapsedSec ?? 0, ref, { allJobsDone });
  }

  const allJobsDone =
    agg.totalJobs > 0 && agg.doneJobs >= agg.totalJobs && agg.runningJobs === 0;

  if (allJobsDone) return 100;
  if (agg.totalJobs === 0) return 12;
  if (agg.percent === 0 && (agg.runningJobs > 0 || agg.pendingJobs > 0)) return 8;
  return agg.percent;
}

export type SyncRateTargetStatus = 'running' | 'pending' | 'failed' | 'done';

export type SyncRateTarget = {
  label: string;
  status: SyncRateTargetStatus;
};

const TARGET_RANK: Record<SyncRateTargetStatus, number> = {
  running: 0,
  pending: 1,
  failed: 2,
  done: 3,
};

function jobTargetStatus(job: RatesSyncJob): SyncRateTargetStatus {
  if (job.status === 'failed' || job.success === false) return 'failed';
  if (job.status === 'completed' || job.status === 'cancelled') return 'done';
  if (job.status === 'running') return 'running';
  return 'pending';
}

/** Libellé RH d’un job — un chip par source, même en sync complète. */
export function resolveJobDisplayLabel(job: RatesSyncJob): string {
  if (job.cotisation_ids && job.cotisation_ids.length > 0) {
    return job.cotisation_ids.map((id) => getCotisationTitle(id)).join(', ');
  }

  const rateKeys = (job.rate_keys ?? []).filter(Boolean);
  if (rateKeys.length === 1 && rateKeys[0] !== 'cotisations') {
    return getCategoryTitle(rateKeys[0]);
  }
  if (rateKeys.length > 0 && !rateKeys.every((key) => key === 'cotisations')) {
    return rateKeys.map((key) => getCategoryTitle(key)).join(', ');
  }

  const sourceName = job.source_name?.trim();
  if (sourceName) return sourceName;
  return job.source_key;
}

function jobMapKey(job: RatesSyncJob): string {
  return job.job_id ?? job.source_key;
}

/**
 * Liste dédupliquée et lisible des taux concernés par les synchronisations en cours,
 * triée par priorité d'affichage (en cours, en attente, échec, terminé).
 */
export function collectSyncRateTargets(statuses: SyncStatusLike[]): SyncRateTarget[] {
  const map = new Map<string, SyncRateTarget>();

  for (const status of statuses) {
    for (const job of status?.jobs ?? []) {
      const mapKey = jobMapKey(job);
      const label = resolveJobDisplayLabel(job);
      const st = jobTargetStatus(job);

      const existing = map.get(mapKey);
      if (!existing || TARGET_RANK[st] < TARGET_RANK[existing.status]) {
        map.set(mapKey, { label, status: st });
      }
    }
  }

  return [...map.values()].sort(
    (a, b) => TARGET_RANK[a.status] - TARGET_RANK[b.status] || a.label.localeCompare(b.label, 'fr'),
  );
}

/** Affichage Restants / Traités pour sync multi-étapes ou mise à jour complète. */
export function shouldPartitionSyncTargets(
  totalJobs: number,
  targetCount: number,
  scopes: Array<RatesSyncTarget['scope']>,
): boolean {
  if (totalJobs > 1 || targetCount > 1) return true;
  return scopes.some((scope) => scope === 'all' || scope === 'rate_keys');
}

export type SyncRateTargetGroups = {
  /** En attente ou en cours de récupération. */
  remaining: SyncRateTarget[];
  /** Terminés avec succès. */
  completed: SyncRateTarget[];
  /** Terminés en échec — le lot continue pour les autres sources. */
  failed: SyncRateTarget[];
};

/** Répartit les taux en restants, validés et en échec (sync multi-étapes). */
export function partitionSyncRateTargets(statuses: SyncStatusLike[]): SyncRateTargetGroups {
  const all = collectSyncRateTargets(statuses);
  const remaining = all.filter((t) => t.status === 'pending' || t.status === 'running');
  const completed = all.filter((t) => t.status === 'done');
  const failed = all.filter((t) => t.status === 'failed');
  return { remaining, completed, failed };
}

export function syncProgressLabel(status: RatesSyncStatusResponse | null | undefined): string {
  const p = status?.progress;
  if (!p) return 'Initialisation…';

  const parts: string[] = [];
  if (p.current_source) {
    parts.push(p.current_source);
  }
  if (p.current_step) {
    parts.push(p.current_step);
  }
  if (parts.length > 0) return parts.join(' — ');

  return `${p.done} / ${p.total} source${p.total > 1 ? 's' : ''}`;
}

export function jobStatusLabel(job: RatesSyncJob): string {
  if (job.status === 'completed' && job.success !== false) return 'Terminé';
  if (job.status === 'failed' || job.success === false) return 'Échec';
  if (job.status === 'cancelled') return 'Annulé';
  if (job.status === 'pending') return 'En attente';
  return job.current_step || 'En cours';
}

export function jobProgressPercent(job: RatesSyncJob): number {
  if (job.status === 'completed' || job.status === 'failed' || job.status === 'cancelled') {
    return 100;
  }
  const frac = job.progress_fraction ?? 0;
  return Math.round(Math.min(99, frac * 100));
}
