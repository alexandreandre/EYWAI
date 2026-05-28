import { RefreshCw, Upload } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { RatesMonthlyAutoPanel } from '@/components/rates/RatesMonthlyAutoPanel';
import type { MonthlyAutoSyncState } from '@/lib/ratesMonthlyAuto';

type RatesPageToolbarProps = {
  onRefresh: () => void;
  onFullSync: () => void;
  isFetching: boolean;
  isSyncing: boolean;
  isMonthlySyncRunning: boolean;
  monthlyState: MonthlyAutoSyncState;
  onMonthlyToggle: (enabled: boolean) => void;
  onRunMonthly: () => void;
  onRestartMonthly: () => void;
};

export function RatesPageToolbar({
  onRefresh,
  onFullSync,
  isFetching,
  isSyncing,
  isMonthlySyncRunning,
  monthlyState,
  onMonthlyToggle,
  onRunMonthly,
  onRestartMonthly,
}: RatesPageToolbarProps) {
  return (
    <div className="flex w-full flex-col gap-3 lg:max-w-xl">
      <div className="flex flex-wrap gap-2">
        <Button
          variant="outline"
          size="sm"
          className="h-9"
          onClick={onRefresh}
          disabled={isFetching}
        >
          <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? 'animate-spin' : ''}`} />
          Actualiser l&apos;affichage
        </Button>
        <Button
          variant="default"
          size="sm"
          className="h-9"
          onClick={onFullSync}
          disabled={isSyncing}
        >
          <Upload className={`mr-2 h-4 w-4 ${isSyncing ? 'animate-pulse' : ''}`} />
          Mise à jour complète
        </Button>
      </div>
      <RatesMonthlyAutoPanel
        state={monthlyState}
        isSyncing={isSyncing}
        isMonthlySyncRunning={isMonthlySyncRunning}
        onToggleEnabled={onMonthlyToggle}
        onRunMonthly={onRunMonthly}
        onRestartMonthly={onRestartMonthly}
      />
    </div>
  );
}
