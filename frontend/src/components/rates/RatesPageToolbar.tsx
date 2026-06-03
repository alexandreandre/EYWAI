import { CloudDownload, RefreshCw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { RatesMonthlyAutoPanel } from '@/components/rates/RatesMonthlyAutoPanel';
import type { MonthlyAutoSyncState } from '@/lib/ratesMonthlyAuto';
import { cn } from '@/lib/utils';

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
  className?: string;
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
  className,
}: RatesPageToolbarProps) {
  return (
    <div
      className={cn(
        'rounded-lg border border-border/80 bg-card p-4',
        className,
      )}
    >
      <div className="grid gap-5 lg:grid-cols-[minmax(0,auto)_minmax(0,1fr)] lg:gap-6 lg:divide-x lg:divide-border/80">
        <div className="flex min-w-0 flex-col gap-2.5 lg:pr-6">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Actions immédiates
          </p>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              className="h-9"
              onClick={onRefresh}
              disabled={isFetching}
            >
              <RefreshCw
                className={cn('mr-2 h-4 w-4 shrink-0', isFetching && 'animate-spin')}
                aria-hidden
              />
              Actualiser l&apos;affichage
            </Button>
            <Button
              variant="default"
              size="sm"
              className="h-9"
              onClick={onFullSync}
              disabled={isSyncing}
            >
              <CloudDownload
                className={cn('mr-2 h-4 w-4 shrink-0', isSyncing && 'animate-pulse')}
                aria-hidden
              />
              Mise à jour complète
            </Button>
          </div>
        </div>

        <div className="flex min-w-0 flex-col gap-2.5 lg:pl-6">
          <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Planification
          </p>
          <RatesMonthlyAutoPanel
            embedded
            state={monthlyState}
            isSyncing={isSyncing}
            isMonthlySyncRunning={isMonthlySyncRunning}
            onToggleEnabled={onMonthlyToggle}
            onRunMonthly={onRunMonthly}
            onRestartMonthly={onRestartMonthly}
          />
        </div>
      </div>
    </div>
  );
}
