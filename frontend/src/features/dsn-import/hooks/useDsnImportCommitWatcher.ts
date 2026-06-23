import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getDsnImportBatch, type DsnImportBatchStatus } from '@/api/dsnImport';
import { applyDsnImportCommitted } from '@/lib/dsnCoverageCache';

/**
 * Continue le suivi d'un import DSN même après fermeture du tiroir (wizard démonté).
 */
export function useDsnImportCommitWatcher(
  batchId: string | null,
  options?: { enabled?: boolean; onFinished?: (status: DsnImportBatchStatus) => void },
) {
  const queryClient = useQueryClient();
  const handledRef = useRef<Set<string>>(new Set());
  const onFinished = options?.onFinished;
  const enabled = Boolean(batchId) && (options?.enabled ?? true);

  const pollQuery = useQuery({
    queryKey: ['dsn-import-poll-bg', batchId],
    queryFn: () => getDsnImportBatch(batchId as string),
    enabled,
    refetchInterval: (query) => {
      const status = query.state.data?.batch?.status as DsnImportBatchStatus | undefined;
      return status === 'committed' || status === 'failed' ? false : 2500;
    },
  });

  useEffect(() => {
    if (!enabled || !batchId || !pollQuery.data) return;
    const status = pollQuery.data.batch.status as DsnImportBatchStatus;
    if (status !== 'committed' && status !== 'failed') return;
    if (handledRef.current.has(batchId)) return;
    handledRef.current.add(batchId);

    if (status === 'committed') {
      void applyDsnImportCommitted(queryClient, pollQuery.data);
    }
    onFinished?.(status);
  }, [batchId, enabled, onFinished, pollQuery.data, queryClient]);

  return pollQuery;
}
