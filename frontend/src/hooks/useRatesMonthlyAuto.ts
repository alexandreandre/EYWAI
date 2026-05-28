import { useCallback, useEffect, useState } from 'react';

import {
  clearMonthlyAutoSyncDone,
  getMonthlyAutoSyncState,
  markMonthlyAutoSyncDone,
  setMonthlyAutoSyncEnabled,
  shouldAutoStartMonthlySync,
  type MonthlyAutoSyncState,
} from '@/lib/ratesMonthlyAuto';

export function useRatesMonthlyAuto() {
  const [state, setState] = useState<MonthlyAutoSyncState>(() => getMonthlyAutoSyncState());

  const refresh = useCallback(() => {
    setState(getMonthlyAutoSyncState());
  }, []);

  const pause = useCallback(() => {
    setMonthlyAutoSyncEnabled(false);
    refresh();
  }, [refresh]);

  const resume = useCallback(() => {
    setMonthlyAutoSyncEnabled(true);
    refresh();
  }, [refresh]);

  const markDone = useCallback(() => {
    markMonthlyAutoSyncDone();
    refresh();
  }, [refresh]);

  const resetCycle = useCallback(() => {
    clearMonthlyAutoSyncDone();
    refresh();
  }, [refresh]);

  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (
        e.key === 'rates_monthly_auto_enabled' ||
        e.key === 'rates_auto_sync_month'
      ) {
        refresh();
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, [refresh]);

  return {
    state,
    refresh,
    pause,
    resume,
    markDone,
    resetCycle,
    shouldAutoStart: shouldAutoStartMonthlySync(),
  };
}
