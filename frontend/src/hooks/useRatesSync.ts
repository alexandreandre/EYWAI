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
  sourceKeysForTarget,
  syncTargetToRequest,
  type RatesSyncTarget,
} from '@/lib/ratesSyncManifest';
import { useRatesSyncSources } from '@/hooks/useRatesSyncSources';
import { useActiveCompanyId } from '@/hooks/queries/useCompanyId';
import type { RatesResponse } from '@/api/rates';

const POLL_MS = 1000;
const TERMINAL = new Set(['completed', 'completed_with_errors', 'failed', 'cancelled']);

type ActiveSync = {
  syncId: string;
  target: RatesSyncTarget;
  status: RatesSyncStatusResponse | null;
  sourceKeys: string[];
  isMonthly: boolean;
};

function normalizeSourceKey(key: string): string {
  return key.trim().toUpperCase().replace(/-/g, '_');
}

export function useRatesSync(onSyncComplete?: (changedKeys: string[]) => void) {
  const companyId = useActiveCompanyId();
  const queryClient = useQueryClient();
  const { data: manifest } = useRatesSyncSources();
  const snapshotRef = useRef<RatesSnapshot | null>(null);
  const pollersRef = useRef<Map<string, ReturnType<typeof setInterval>>>(new Map());

  const [activeSyncs, setActiveSyncs] = useState<ActiveSync[]>([]);
  const [syncError, setSyncError] = useState<string | null>(null);

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

  const finalizeWhenIdle = useCallback(
    async (lastStatus: RatesSyncStatusResponse, markMonthlyDone: boolean) => {
      await queryClient.refetchQueries({ queryKey: queryKeys.rates(companyId) });
      await queryClient.invalidateQueries({
        queryKey: [...queryKeys.rates(companyId), 'sync-sources'],
      });

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
        toast.warning('Mise à jour terminée avec des erreurs sur certaines sources');
      } else if (lastStatus.status === 'failed') {
        toast.error('La mise à jour a échoué');
      } else if (lastStatus.status === 'cancelled') {
        toast.info('Mise à jour annulée');
      }

      if (markMonthlyDone) {
        markMonthlyAutoSyncDone();
      }

      snapshotRef.current = null;
      onSyncComplete?.(changed);
    },
    [companyId, onSyncComplete, queryClient],
  );

  const finishSync = useCallback(
    async (syncId: string, finalStatus: RatesSyncStatusResponse) => {
      stopPoller(syncId);

      setActiveSyncs((prev) => {
        const finished = prev.find((s) => s.syncId === syncId);
        const wasMonthly = finished?.isMonthly ?? false;
        const next = prev.filter((s) => s.syncId !== syncId);
        const anyStillRunning = next.some(
          (s) => !s.status || !TERMINAL.has(s.status.status),
        );
        if (!anyStillRunning) {
          void finalizeWhenIdle(finalStatus, wasMonthly);
        }
        return next;
      });
    },
    [finalizeWhenIdle, stopPoller],
  );

  const invalidateSyncManifest = useCallback(async () => {
    await queryClient.invalidateQueries({
      queryKey: [...queryKeys.rates(companyId), 'sync-sources'],
    });
  }, [companyId, queryClient]);

  const cancelSync = useCallback(
    async (syncId: string) => {
      stopPoller(syncId);
      try {
        await cancelRatesSync(syncId);
        setActiveSyncs((prev) => {
          const cancelled = prev.find((s) => s.syncId === syncId);
          const next = prev.filter((s) => s.syncId !== syncId);
          const anyStillRunning = next.some(
            (s) => !s.status || !TERMINAL.has(s.status.status),
          );
          if (!anyStillRunning && cancelled) {
            snapshotRef.current = null;
          }
          return next;
        });
        await invalidateSyncManifest();
        toast.info('Mise à jour annulée');
      } catch (e) {
        const { message } = parseRatesError(e);
        setActiveSyncs((prev) => prev.filter((s) => s.syncId !== syncId));
        await invalidateSyncManifest();
        toast.error(message || 'Impossible d’annuler la mise à jour');
      }
    },
    [invalidateSyncManifest, stopPoller],
  );

  const cancelAllSyncs = useCallback(async () => {
    const ids = activeSyncs.map((s) => s.syncId);
    stopAllPollers();
    await Promise.allSettled(ids.map((id) => cancelRatesSync(id)));
    setActiveSyncs([]);
    snapshotRef.current = null;
    await invalidateSyncManifest();
    toast.info('Mises à jour annulées');
  }, [activeSyncs, invalidateSyncManifest, stopAllPollers]);

  const pollStatus = useCallback(
    (syncId: string) => {
      stopPoller(syncId);
      const interval = setInterval(async () => {
        try {
          const next = await getRatesSyncStatus(syncId);
          setActiveSyncs((prev) =>
            prev.map((s) => (s.syncId === syncId ? { ...s, status: next } : s)),
          );
          if (TERMINAL.has(next.status)) {
            await finishSync(syncId, next);
          }
        } catch (e) {
          const { message } = parseRatesError(e);
          setSyncError(message);
          stopPoller(syncId);
          setActiveSyncs((prev) => prev.filter((s) => s.syncId !== syncId));
          toast.error(message);
        }
      }, POLL_MS);
      pollersRef.current.set(syncId, interval);
    },
    [finishSync, stopPoller],
  );

  const isSourceRunning = useCallback(
    (sourceKey: string) => {
      const norm = normalizeSourceKey(sourceKey);
      return activeSyncs.some(
        (s) =>
          s.sourceKeys.some((k) => normalizeSourceKey(k) === norm) &&
          (!s.status || !TERMINAL.has(s.status.status)),
      );
    },
    [activeSyncs],
  );

  const isTargetRunning = useCallback(
    (target: RatesSyncTarget) => {
      const keys = sourceKeysForTarget(manifest, target);
      if (keys.length === 0) return false;
      return keys.some((k) => isSourceRunning(k));
    },
    [isSourceRunning, manifest],
  );

  const isRateKeyRunning = useCallback(
    (rateKey: string) => isTargetRunning({ scope: 'rate_key', rateKey }),
    [isTargetRunning],
  );

  const isCotisationRunning = useCallback(
    (cotisationId: string) =>
      isTargetRunning({ scope: 'cotisation_id', cotisationId }),
    [isTargetRunning],
  );

  const startSync = useCallback(
    async (target: RatesSyncTarget, options?: { monthly?: boolean; snapshot?: RatesSnapshot }) => {
      const keys = sourceKeysForTarget(manifest, target);
      if (target.scope !== 'all' && keys.length === 0) {
        toast.error('Aucune source de mise à jour disponible pour cet élément.');
        return;
      }
      if (keys.some((k) => isSourceRunning(k))) {
        toast.info('Une mise à jour est déjà en cours pour cette source.');
        return;
      }

      setSyncError(null);
      const isMonthly = Boolean(options?.monthly);

      if (!snapshotRef.current) {
        const current = queryClient.getQueryData<RatesResponse>(queryKeys.rates(companyId));
        snapshotRef.current =
          options?.snapshot ?? (current ? buildRatesSnapshot(current) : {});
      }

      try {
        const started = await startRatesSync(syncTargetToRequest(target));
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
          },
        };
        setActiveSyncs((prev) => [...prev, entry]);
        pollStatus(started.sync_id);
      } catch (e) {
        const { message } = parseRatesError(e);
        setSyncError(message);
        toast.error(message);
      }
    },
    [companyId, isSourceRunning, manifest, pollStatus, queryClient],
  );

  useEffect(() => () => stopAllPollers(), [stopAllPollers]);

  const isSyncing = activeSyncs.length > 0;

  const isMonthlySyncRunning = activeSyncs.some(
    (s) => s.isMonthly && (!s.status || !TERMINAL.has(s.status.status)),
  );

  return {
    startSync,
    cancelSync,
    cancelAllSyncs,
    isSyncing,
    isMonthlySyncRunning,
    isSourceRunning,
    isTargetRunning,
    isRateKeyRunning,
    isCotisationRunning,
    syncError,
    activeSyncs,
    manifest,
    clearSyncError: () => setSyncError(null),
  };
}
