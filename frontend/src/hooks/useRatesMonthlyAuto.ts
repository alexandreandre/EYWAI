import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import {
  fetchMonthlyRatesState,
  updateMonthlyRatesEnabled,
  type MonthlyRatesRun,
} from '@/api/rates';
import { queryKeys } from '@/lib/queryKeys';

export type MonthlyAutoSyncState = {
  enabled: boolean;
  statusLabel: string;
  showRun: boolean;
  showRestart: boolean;
  runButtonLabel: string;
  run: MonthlyRatesRun | null;
};

export function useRatesMonthlyAuto() {
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: queryKeys.ratesMonthly(),
    queryFn: fetchMonthlyRatesState,
  });
  const data = query.data;

  const mutation = useMutation({
    mutationFn: updateMonthlyRatesEnabled,
    onSuccess: (next) => {
      queryClient.setQueryData(queryKeys.ratesMonthly(), next);
    },
  });

  const state: MonthlyAutoSyncState = {
    enabled: data?.enabled ?? true,
    statusLabel: query.isError
      ? 'Planification indisponible pour le moment.'
      : (data?.status_label ?? 'Chargement de la planification…'),
    showRun: Boolean(data?.show_run),
    showRestart: Boolean(data?.show_restart),
    runButtonLabel: data?.run_button_label ?? 'Lancer la mise à jour du mois',
    run: data?.run ?? null,
  };

  return {
    state,
    refresh: () => {
      void query.refetch();
    },
    setEnabled: mutation.mutateAsync,
  };
}
