import { CalendarClock, Play, RotateCcw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import type { MonthlyAutoSyncState } from '@/lib/ratesMonthlyAuto';
import { RATES_UPDATES_LOCK_REASON } from '@/lib/ratesUpdatesLock';
import { cn } from '@/lib/utils';

type RatesMonthlyAutoPanelProps = {
  state: MonthlyAutoSyncState;
  isSyncing: boolean;
  isMonthlySyncRunning: boolean;
  onToggleEnabled: (enabled: boolean) => void;
  onRunMonthly: () => void;
  onRestartMonthly: () => void;
  /** Verrouille les lancements manuels ; l'interrupteur reste utilisable. */
  updatesLocked?: boolean;
  /** Intégré dans la barre de commandes unifiée (sans bordure propre). */
  embedded?: boolean;
};

export function RatesMonthlyAutoPanel({
  state,
  isSyncing,
  isMonthlySyncRunning,
  onToggleEnabled,
  onRunMonthly,
  onRestartMonthly,
  updatesLocked = false,
  embedded = false,
}: RatesMonthlyAutoPanelProps) {
  const showRunMonthly =
    state.enabled && state.isFirstDayOfMonth && !state.completedThisMonth && !isSyncing;
  const showRestart =
    state.enabled && state.isFirstDayOfMonth && state.completedThisMonth && !isSyncing;

  return (
    <div
      className={cn(
        'flex min-w-0 gap-3',
        !embedded && 'rounded-lg border border-border/80 bg-card p-4',
      )}
    >
      <div
        className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border/80 bg-muted/40"
        aria-hidden
      >
        <CalendarClock className="h-4 w-4 text-muted-foreground" />
      </div>

      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <Label
            htmlFor="rates-monthly-auto"
            className="cursor-pointer text-sm font-medium leading-snug"
          >
            Mise à jour automatique le 1er du mois
          </Label>
          <Switch
            id="rates-monthly-auto"
            checked={state.enabled}
            onCheckedChange={onToggleEnabled}
            disabled={isMonthlySyncRunning}
            className="shrink-0"
          />
        </div>

        <div className="flex flex-wrap items-center gap-x-2 gap-y-2">
          <p className="text-xs leading-relaxed text-muted-foreground">{state.statusLabel}</p>
          {showRunMonthly && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="h-7 shrink-0 px-2.5 text-xs"
              onClick={onRunMonthly}
              disabled={updatesLocked}
              title={updatesLocked ? RATES_UPDATES_LOCK_REASON : undefined}
            >
              <Play className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              Lancer la mise à jour du mois
            </Button>
          )}
          {showRestart && (
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="h-7 shrink-0 px-2.5 text-xs"
              onClick={onRestartMonthly}
              disabled={updatesLocked}
              title={updatesLocked ? RATES_UPDATES_LOCK_REASON : undefined}
            >
              <RotateCcw className="mr-1.5 h-3.5 w-3.5" aria-hidden />
              Recommencer
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
