import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import {
  cancelRatesSync,
  getRatesSyncStatus,
  startRatesSync,
  type RatesSyncStatusResponse,
} from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';
import { markMonthlyAutoSyncDone } from '@/lib/ratesMonthlyAuto';
import {
  buildRatesSnapshot,
  countChangedCategories,
  parseRatesError,
  type RatesSnapshot,
} from '@/lib/ratesUtils';
import {
  activeSyncCoversRateKey,
  activeSyncCoversSourceKey,
  collectRunningSyncIdsFromManifest,
  isCotisationRunningInSync,
  sourcesForCotisationId,
  sourcesForRateKey,
  sourceKeysForTarget,
  syncRequestToTarget,
  syncTargetToRequest,
  type RatesSyncTarget,
} from '@/lib/ratesSyncManifest';
import {
  applyCompletedSyncJobsToRatesCache,
} from '@/lib/ratesLastCheckedCache';
import { humanizeSyncError } from '@/lib/ratesSyncOutcome';
import {
  findPersistedSyncSession,
  readPersistedSyncIds,
  readPersistedSyncSessions,
  removePersistedSyncId,
  writePersistedSyncSessions,
  type PersistedSyncSession,
} from '@/lib/ratesSyncStorage';
import {
  recordSyncDurationFromStatus,
} from '@/lib/ratesSyncDurationStorage';
import { useRatesSyncSources } from '@/hooks/useRatesSyncSources';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import type { RatesResponse } from '@/api/rates';

const POLL_MS = 1000;
const TERMINAL = new Set(['completed', 'completed_with_errors', 'failed', 'cancelled']);
const OPTIMISTIC_SYNC_PREFIX = 'pending:';

type ActiveSync = {
  syncId: string;
  target: RatesSyncTarget;
  status: RatesSyncStatusResponse | null;
  sourceKeys: string[];
  isMonthly: boolean;
  isOptimistic?: boolean;
};

function isOptimisticSyncId(syncId: string): boolean {
  return syncId.startsWith(OPTIMISTIC_SYNC_PREFIX);
}

function buildOptimisticSyncEntry(
  target: RatesSyncTarget,
  sourceKeys: string[],
  isMonthly: boolean,
  totalJobs: number,
): ActiveSync {
  const syncId = `${OPTIMISTIC_SYNC_PREFIX}${crypto.randomUUID()}`;
  return {
    syncId,
    target,
    isMonthly,
    sourceKeys,
    isOptimistic: true,
    status: {
      sync_id: syncId,
      status: 'running',
      progress: {
        total: totalJobs,
        completed: 0,
        failed: 0,
        running: totalJobs,
        done: 0,
        percent: 0,
      },
      jobs: sourceKeys.map((source_key) => ({
        source_key,
        source_name: source_key,
        job_id: null,
        status: 'running',
        ...(target.scope === 'cotisation_id'
          ? { cotisation_ids: [target.cotisationId] }
          : target.scope === 'cotisation_bundle'
            ? { cotisation_ids: target.cotisationIds }
            : {}),
      })),
      created_at: new Date().toISOString(),
      target: syncTargetToRequest(target),
    },
  };
}

function normalizeSourceKey(key: string): string {
  return key.trim().toUpperCase().replace(/-/g, '_');
}

function isSyncEntryActive(entry: ActiveSync): boolean {
  return !entry.status || !TERMINAL.has(entry.status.status);
}

/** Bandeau « en cours » : masqué en finalisation (jobs terminés, statut lot encore running). */
function shouldShowSyncProgress(entry: ActiveSync): boolean {
  if (!isSyncEntryActive(entry)) return false;

  const status = entry.status;
  if (!status) return true;

  const { progress, jobs } = status;
  if (progress.total > 0 && progress.running === 0 && progress.done >= progress.total) {
    return false;
  }

  if (
    jobs.length > 0 &&
    jobs.every((job) => job.status !== 'running' && job.status !== 'pending')
  ) {
    return false;
  }

  return true;
}

function buildResumedSyncEntry(session: PersistedSyncSession): ActiveSync {
  return {
    syncId: session.syncId,
    target: session.target,
    isMonthly: session.isMonthly,
    sourceKeys: [],
    status: session.createdAt
      ? {
          sync_id: session.syncId,
          status: 'running',
          progress: {
            total: 1,
            completed: 0,
            failed: 0,
            running: 1,
            done: 0,
            percent: 0,
          },
          jobs: [],
          created_at: session.createdAt,
          target: syncTargetToRequest(session.target),
        }
      : null,
  };
}

function hydrateActiveSyncsFromStorage(): ActiveSync[] {
  return readPersistedSyncSessions().map(buildResumedSyncEntry);
}

function toPersistedSession(entry: ActiveSync): PersistedSyncSession {
  return {
    syncId: entry.syncId,
    target: entry.target,
    isMonthly: entry.isMonthly,
    createdAt: entry.status?.created_at ?? undefined,
  };
}

export function useRatesSync(onSyncComplete?: (changedKeys: string[]) => void) {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const { data: manifest } = useRatesSyncSources();
  const snapshotRef = useRef<RatesSnapshot | null>(null);
  const pollersRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());
  const attachedSyncIdsRef = useRef<Set<string>>(new Set());
  /** Lots arrêtés par l'utilisateur — ignore polls / reprise manifeste tant que le serveur rattrape. */
  const suppressedSyncIdsRef = useRef<Set<string>>(new Set());
  /** Évite de traiter deux fois la fin d’un même lot (poll concurrent, focus onglet…). */
  const finishedSyncIdsRef = useRef<Set<string>>(new Set());
  /** Incrémenté à chaque nouveau lot ou annulation — invalide les finalizeWhenIdle en cours. */
  const finalizeGenerationRef = useRef(0);
  /** Si l’utilisateur ferme la bannière avant la fin du refetch, ne pas la réafficher. */
  const outcomeDismissedGenerationRef = useRef<number | null>(null);
  const ratesRefetchTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const [activeSyncs, setActiveSyncs] = useState<ActiveSync[]>(hydrateActiveSyncsFromStorage);
  const [syncError, setSyncError] = useState<string | null>(null);
  const [syncOutcome, setSyncOutcome] = useState<RatesSyncStatusResponse | null>(null);

  const persistActiveSyncIds = useCallback((entries: ActiveSync[]) => {
    writePersistedSyncSessions(
      entries
        .filter(isSyncEntryActive)
        .filter((s) => !isOptimisticSyncId(s.syncId))
        .map(toPersistedSession),
    );
  }, []);

  const stopPoller = useCallback((syncId: string) => {
    const interval = pollersRef.current.get(syncId);
    if (interval) {
      clearInterval(interval);
      pollersRef.current.delete(syncId);
    }
  }, []);

  const stopAllPollers = useCallback(() => {
    pollersRef.current.forEach((interval) => clearInterval(interval));
    pollersRef.current.clear();
  }, []);

  const scheduleRatesRefetch = useCallback(() => {
    if (ratesRefetchTimerRef.current) {
      clearTimeout(ratesRefetchTimerRef.current);
    }
    ratesRefetchTimerRef.current = setTimeout(() => {
      ratesRefetchTimerRef.current = null;
      void queryClient.invalidateQueries({ queryKey: queryKeys.rates(companyId) });
    }, 350);
  }, [companyId, queryClient]);

  const refetchRatesNow = useCallback(async () => {
    if (ratesRefetchTimerRef.current) {
      clearTimeout(ratesRefetchTimerRef.current);
      ratesRefetchTimerRef.current = null;
    }
    await queryClient.invalidateQueries({ queryKey: queryKeys.rates(companyId) });
    await queryClient.refetchQueries({ queryKey: queryKeys.rates(companyId) });
  }, [companyId, queryClient]);

  const notifyRatesDataRefresh = useCallback(() => {
    const fresh = queryClient.getQueryData<RatesResponse>(queryKeys.rates(companyId));
    const changed =
      snapshotRef.current && fresh
        ? countChangedCategories(snapshotRef.current, fresh)
        : [];
    if (changed.length > 0) {
      onSyncComplete?.(changed);
    }
  }, [companyId, onSyncComplete, queryClient]);

  const finalizeWhenIdle = useCallback(
    async (
      lastStatus: RatesSyncStatusResponse,
      markMonthlyDone: boolean,
      generation: number,
    ) => {
      await refetchRatesNow();
      await queryClient.invalidateQueries({
        queryKey: [...queryKeys.rates(companyId), 'sync-sources'],
      });

      if (generation !== finalizeGenerationRef.current) {
        return;
      }

      const fresh = queryClient.getQueryData<RatesResponse>(queryKeys.rates(companyId));
      const changed =
        snapshotRef.current && fresh
          ? countChangedCategories(snapshotRef.current, fresh)
          : [];

      if (changed.length > 0) {
        toast.success(
          `${changed.length} référentiel${changed.length > 1 ? 's' : ''} mis à jour`,
        );
      } else if (lastStatus.status === 'completed') {
        toast.info('Contrôle terminé — aucune modification détectée');
      } else if (lastStatus.status === 'completed_with_errors') {
        const failed = lastStatus.jobs.filter(
          (j) => j.status === 'failed' || (j.status === 'completed' && j.success === false),
        );
        const names = failed.map((j) => j.source_name).slice(0, 3).join(', ');
        toast.warning(
          failed.length > 0
            ? `Mise à jour partielle — échec : ${names}${failed.length > 3 ? '…' : ''}`
            : 'Mise à jour terminée avec des erreurs sur certaines sources',
        );
      } else if (lastStatus.status === 'failed') {
        const first = lastStatus.jobs.find(
          (j) => j.status === 'failed' || (j.status === 'completed' && j.success === false),
        );
        toast.error(
          first
            ? `Échec — ${first.source_name} : ${humanizeSyncError(first.error_message)}`
            : 'La mise à jour a échoué',
        );
      } else if (lastStatus.status === 'cancelled') {
        toast.info('Mise à jour annulée');
      }

      if (outcomeDismissedGenerationRef.current !== generation) {
        setSyncOutcome(lastStatus);
      }

      if (markMonthlyDone) {
        markMonthlyAutoSyncDone();
      }

      snapshotRef.current = null;
      onSyncComplete?.(changed);
    },
    [companyId, onSyncComplete, queryClient, refetchRatesNow],
  );

  const finishSync = useCallback(
    async (syncId: string, finalStatus: RatesSyncStatusResponse) => {
      if (finishedSyncIdsRef.current.has(syncId)) return;
      finishedSyncIdsRef.current.add(syncId);

      stopPoller(syncId);
      attachedSyncIdsRef.current.delete(syncId);
      removePersistedSyncId(syncId);

      if (suppressedSyncIdsRef.current.has(syncId)) {
        suppressedSyncIdsRef.current.delete(syncId);
        setActiveSyncs((prev) => {
          const next = prev.filter((s) => s.syncId !== syncId);
          persistActiveSyncIds(next);
          return next;
        });
        return;
      }

      let wasMonthly = false;
      let anyStillRunning = true;

      setActiveSyncs((prev) => {
        const finished = prev.find((s) => s.syncId === syncId);
        if (finished && TERMINAL.has(finalStatus.status)) {
          recordSyncDurationFromStatus(finished.target, finalStatus);
        }
        wasMonthly = finished?.isMonthly ?? false;
        const next = prev.filter((s) => s.syncId !== syncId);
        persistActiveSyncIds(next);
        anyStillRunning = next.some(isSyncEntryActive);
        return next;
      });

      await refetchRatesNow();
      applyCompletedSyncJobsToRatesCache(queryClient, companyId, finalStatus.jobs);

      if (!anyStillRunning) {
        await finalizeWhenIdle(finalStatus, wasMonthly, finalizeGenerationRef.current);
      } else {
        notifyRatesDataRefresh();
      }
    },
    [
      finalizeWhenIdle,
      notifyRatesDataRefresh,
      persistActiveSyncIds,
      refetchRatesNow,
      stopPoller,
    ],
  );

  const invalidateSyncManifest = useCallback(async () => {
    await queryClient.invalidateQueries({
      queryKey: [...queryKeys.rates(companyId), 'sync-sources'],
    });
  }, [companyId, queryClient]);

  const pollStatus = useCallback(
    (syncId: string) => {
      stopPoller(syncId);

      const tick = async () => {
        if (suppressedSyncIdsRef.current.has(syncId)) return;

        try {
          const next = await getRatesSyncStatus(syncId);
          if (suppressedSyncIdsRef.current.has(syncId)) return;

          let shouldRefetchRates = false;
          setActiveSyncs((prev) => {
            const current = prev.find((s) => s.syncId === syncId);
            const prevDone = current?.status?.progress?.done ?? 0;
            const nextDone = next.progress?.done ?? 0;
            if (!TERMINAL.has(next.status) && nextDone > prevDone) {
              shouldRefetchRates = true;
            }
            const updated = prev.map((s) => (s.syncId === syncId ? { ...s, status: next } : s));
            persistActiveSyncIds(updated);
            return updated;
          });

          if (shouldRefetchRates) {
            applyCompletedSyncJobsToRatesCache(queryClient, companyId, next.jobs);
            scheduleRatesRefetch();
            notifyRatesDataRefresh();
          }

          if (TERMINAL.has(next.status) && !finishedSyncIdsRef.current.has(syncId)) {
            await finishSync(syncId, next);
          }
        } catch (e) {
          const { message } = parseRatesError(e);
          setSyncError(message);
          stopPoller(syncId);
          attachedSyncIdsRef.current.delete(syncId);
          removePersistedSyncId(syncId);
          setActiveSyncs((prev) => {
            const next = prev.filter((s) => s.syncId !== syncId);
            persistActiveSyncIds(next);
            return next;
          });
          toast.error(message);
        }
      };

      void tick();
      const interval = setInterval(() => void tick(), POLL_MS);
      pollersRef.current.set(syncId, interval);
    },
    [
      finishSync,
      notifyRatesDataRefresh,
      persistActiveSyncIds,
      scheduleRatesRefetch,
      stopPoller,
    ],
  );

  const attachExistingSync = useCallback(
    async (syncId: string, options?: { isMonthly?: boolean }) => {
      if (suppressedSyncIdsRef.current.has(syncId)) return;
      if (attachedSyncIdsRef.current.has(syncId)) return;

      const persisted = findPersistedSyncSession(syncId);

      try {
        const status = await getRatesSyncStatus(syncId);
        if (TERMINAL.has(status.status)) {
          removePersistedSyncId(syncId);
          setActiveSyncs((prev) => prev.filter((s) => s.syncId !== syncId));
          return;
        }

        attachedSyncIdsRef.current.add(syncId);
        const target = status.target
          ? syncRequestToTarget(status.target)
          : (persisted?.target ?? { scope: 'all' });
        const isMonthly = options?.isMonthly ?? persisted?.isMonthly ?? false;

        setActiveSyncs((prev) => {
          const existing = prev.find((s) => s.syncId === syncId);
          const entry: ActiveSync = {
            syncId,
            target: existing?.target ?? target,
            isMonthly: existing?.isMonthly ?? isMonthly,
            sourceKeys: status.jobs.map((j) => j.source_key),
            status,
          };
          const next = existing
            ? prev.map((s) => (s.syncId === syncId ? entry : s))
            : [...prev, entry];
          persistActiveSyncIds(next);
          return next;
        });
        pollStatus(syncId);
      } catch {
        attachedSyncIdsRef.current.delete(syncId);
        removePersistedSyncId(syncId);
        setActiveSyncs((prev) => prev.filter((s) => s.syncId !== syncId));
      }
    },
    [persistActiveSyncIds, pollStatus],
  );

  /** Reprend le suivi après rechargement ou retour sur la page (sessionStorage + manifeste). */
  useEffect(() => {
    const syncIds = [
      ...new Set([
        ...readPersistedSyncIds(),
        ...(manifest ? collectRunningSyncIdsFromManifest(manifest) : []),
      ]),
    ];

    for (const syncId of syncIds) {
      void attachExistingSync(syncId);
    }
  }, [manifest, attachExistingSync]);

  /** Libère les syncs supprimées une fois absentes du manifeste serveur. */
  useEffect(() => {
    if (!manifest) return;
    const running = new Set(collectRunningSyncIdsFromManifest(manifest));
    for (const syncId of suppressedSyncIdsRef.current) {
      if (!running.has(syncId)) {
        suppressedSyncIdsRef.current.delete(syncId);
      }
    }
  }, [manifest]);

  /** Rafraîchit l'état au retour sur l'onglet / la page. */
  useEffect(() => {
    const refreshRunningSyncs = () => {
      if (document.visibilityState !== 'visible') return;

      void queryClient.invalidateQueries({
        queryKey: [...queryKeys.rates(companyId), 'sync-sources'],
      });

      for (const syncId of readPersistedSyncIds()) {
        if (suppressedSyncIdsRef.current.has(syncId)) continue;
        if (!attachedSyncIdsRef.current.has(syncId)) {
          void attachExistingSync(syncId);
          continue;
        }
        void getRatesSyncStatus(syncId)
          .then((status) => {
            if (TERMINAL.has(status.status)) {
              void finishSync(syncId, status);
              return;
            }
            setActiveSyncs((prev) => {
              const updated = prev.map((s) =>
                s.syncId === syncId ? { ...s, status } : s,
              );
              persistActiveSyncIds(updated);
              return updated;
            });
          })
          .catch(() => {
            removePersistedSyncId(syncId);
            setActiveSyncs((prev) => prev.filter((s) => s.syncId !== syncId));
          });
      }
    };

    document.addEventListener('visibilitychange', refreshRunningSyncs);
    window.addEventListener('focus', refreshRunningSyncs);
    return () => {
      document.removeEventListener('visibilitychange', refreshRunningSyncs);
      window.removeEventListener('focus', refreshRunningSyncs);
    };
  }, [attachExistingSync, companyId, finishSync, persistActiveSyncIds, queryClient]);

  const cancelSync = useCallback(
    async (syncId: string) => {
      suppressedSyncIdsRef.current.add(syncId);
      stopPoller(syncId);
      attachedSyncIdsRef.current.delete(syncId);
      removePersistedSyncId(syncId);

      setActiveSyncs((prev) => {
        const next = prev.filter((s) => s.syncId !== syncId);
        const anyStillRunning = next.some(isSyncEntryActive);
        if (!anyStillRunning) {
          snapshotRef.current = null;
          finalizeGenerationRef.current += 1;
          outcomeDismissedGenerationRef.current = null;
          setSyncOutcome(null);
        }
        persistActiveSyncIds(next);
        return next;
      });

      if (isOptimisticSyncId(syncId)) {
        return;
      }

      try {
        await cancelRatesSync(syncId);
        await invalidateSyncManifest();
        toast.info('Mise à jour annulée');
      } catch (e) {
        const { message } = parseRatesError(e);
        await invalidateSyncManifest();
        toast.error(message || 'Impossible d’annuler la mise à jour');
      }
    },
    [invalidateSyncManifest, persistActiveSyncIds, stopPoller],
  );

  const cancelAllSyncs = useCallback(async () => {
    for (const entry of activeSyncs) {
      suppressedSyncIdsRef.current.add(entry.syncId);
    }
    const realIds = activeSyncs
      .filter((s) => !isOptimisticSyncId(s.syncId))
      .map((s) => s.syncId);
    stopAllPollers();
    attachedSyncIdsRef.current.clear();
    writePersistedSyncSessions([]);
    setActiveSyncs([]);
    finalizeGenerationRef.current += 1;
    outcomeDismissedGenerationRef.current = null;
    setSyncOutcome(null);
    setSyncError(null);
    snapshotRef.current = null;
    if (realIds.length > 0) {
      await Promise.allSettled(realIds.map((id) => cancelRatesSync(id)));
    }
    await invalidateSyncManifest();
    toast.info('Mises à jour annulées');
  }, [activeSyncs, invalidateSyncManifest, stopAllPollers]);

  const isSourceRunningInManifest = useCallback(
    (sourceKey: string) => {
      if (!manifest) return false;
      const norm = normalizeSourceKey(sourceKey);
      for (const cat of manifest.rate_categories) {
        for (const src of cat.sources) {
          if (normalizeSourceKey(src.source_key) === norm && src.is_running) return true;
        }
        for (const unit of cat.cotisation_units ?? []) {
          for (const src of unit.sources) {
            if (normalizeSourceKey(src.source_key) === norm && src.is_running) return true;
          }
        }
      }
      return false;
    },
    [manifest],
  );

  /** Spinner UI menu source : sync explicite ou reprise manifeste (même source). */
  const isSourceRunning = useCallback(
    (sourceKey: string) => {
      const explicit = activeSyncs.some(
        (s) => isSyncEntryActive(s) && activeSyncCoversSourceKey(s.target, sourceKey),
      );
      return explicit || isSourceRunningInManifest(sourceKey);
    },
    [activeSyncs, isSourceRunningInManifest],
  );

  /** Spinner UI carte barème / section rate_key : cible de sync explicite uniquement. */
  const isTargetRunning = useCallback(
    (target: RatesSyncTarget) => {
      if (target.scope === 'rate_key') {
        return activeSyncs.some(
          (s) => isSyncEntryActive(s) && activeSyncCoversRateKey(s.target, target.rateKey),
        );
      }
      if (target.scope === 'rate_keys') {
        return activeSyncs.some(
          (s) =>
            isSyncEntryActive(s) &&
            target.rateKeys.some((rk) => activeSyncCoversRateKey(s.target, rk)),
        );
      }
      return false;
    },
    [activeSyncs],
  );

  const isRateKeyRunning = useCallback(
    (rateKey: string) => {
      if (isTargetRunning({ scope: 'rate_key', rateKey })) return true;
      return sourcesForRateKey(manifest, rateKey).some((s) => s.is_running);
    },
    [isTargetRunning, manifest],
  );

  const isCotisationRunning = useCallback(
    (cotisationId: string) => {
      const inActive = activeSyncs.some((entry) => {
        if (!isSyncEntryActive(entry)) return false;
        return isCotisationRunningInSync(
          manifest,
          { target: entry.target, jobs: entry.status?.jobs },
          cotisationId,
        );
      });
      if (inActive) return true;
      return sourcesForCotisationId(manifest, cotisationId).some((s) => s.is_running);
    },
    [activeSyncs, manifest],
  );

  const isGlobalSyncInFlight = useCallback(() => {
    return (
      activeSyncs.some(isSyncEntryActive) ||
      collectRunningSyncIdsFromManifest(manifest).length > 0
    );
  }, [activeSyncs, manifest]);

  const startSync = useCallback(
    async (target: RatesSyncTarget, options?: { monthly?: boolean; snapshot?: RatesSnapshot }) => {
      const keys = sourceKeysForTarget(manifest, target);
      if (target.scope !== 'all' && keys.length === 0) {
        toast.error(
          target.scope === 'rate_keys'
            ? 'Aucune source de mise à jour disponible pour cette section.'
            : 'Aucune source de mise à jour disponible pour cet élément.',
        );
        return;
      }
      if (isGlobalSyncInFlight()) {
        const runningIds = collectRunningSyncIdsFromManifest(manifest);
        for (const syncId of runningIds) {
          await attachExistingSync(syncId, { isMonthly: options?.monthly });
        }
        toast.info('Une mise à jour est déjà en cours.');
        return;
      }

      setSyncError(null);
      finalizeGenerationRef.current += 1;
      outcomeDismissedGenerationRef.current = null;
      setSyncOutcome(null);
      const isMonthly = Boolean(options?.monthly);

      if (!snapshotRef.current) {
        const current = queryClient.getQueryData<RatesResponse>(queryKeys.rates(companyId));
        snapshotRef.current =
          options?.snapshot ?? (current ? buildRatesSnapshot(current) : {});
      }

      const totalJobs =
        target.scope === 'all'
          ? Math.max(keys.length, manifest?.all_critical_count ?? 1)
          : Math.max(keys.length, 1);

      const optimisticEntry = buildOptimisticSyncEntry(target, keys, isMonthly, totalJobs);
      setActiveSyncs((prev) => [...prev, optimisticEntry]);

      try {
        const started = await startRatesSync(syncTargetToRequest(target));
        attachedSyncIdsRef.current.add(started.sync_id);
        const entry: ActiveSync = {
          syncId: started.sync_id,
          target,
          isMonthly,
          sourceKeys: started.jobs.map((j) => j.source_key),
          status: {
            sync_id: started.sync_id,
            status: 'running',
            progress: {
              total: started.total,
              completed: 0,
              failed: 0,
              running: started.total,
              done: 0,
              percent: 0,
            },
            jobs: started.jobs,
            created_at: new Date().toISOString(),
            target: syncTargetToRequest(target),
          },
        };
        setActiveSyncs((prev) => {
          const next = [
            ...prev.filter((s) => s.syncId !== optimisticEntry.syncId),
            entry,
          ];
          persistActiveSyncIds(next);
          return next;
        });
        void invalidateSyncManifest();
        pollStatus(started.sync_id);
      } catch (e) {
        setActiveSyncs((prev) => prev.filter((s) => s.syncId !== optimisticEntry.syncId));
        const { message } = parseRatesError(e);
        setSyncError(message);
        toast.error(message);
      }
    },
    [
      attachExistingSync,
      companyId,
      invalidateSyncManifest,
      isGlobalSyncInFlight,
      manifest,
      persistActiveSyncIds,
      pollStatus,
      queryClient,
    ],
  );

  useEffect(
    () => () => {
      stopAllPollers();
      if (ratesRefetchTimerRef.current) {
        clearTimeout(ratesRefetchTimerRef.current);
      }
    },
    [stopAllPollers],
  );

  const isSyncProgressVisible = activeSyncs.some(shouldShowSyncProgress);

  const isSyncing =
    isSyncProgressVisible ||
    collectRunningSyncIdsFromManifest(manifest).length > 0;

  const isMonthlySyncRunning = activeSyncs.some(
    (s) => s.isMonthly && isSyncEntryActive(s),
  );

  return {
    startSync,
    cancelSync,
    cancelAllSyncs,
    isSyncing,
    isSyncProgressVisible,
    isMonthlySyncRunning,
    isSourceRunning,
    isTargetRunning,
    isRateKeyRunning,
    isCotisationRunning,
    syncError,
    syncOutcome,
    activeSyncs,
    manifest,
    clearSyncError: () => setSyncError(null),
    dismissSyncOutcome: () => {
      outcomeDismissedGenerationRef.current = finalizeGenerationRef.current;
      setSyncOutcome(null);
    },
  };
}
