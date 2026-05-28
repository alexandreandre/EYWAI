import { CalendarClock, Play, RotateCcw } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import type { MonthlyAutoSyncState } from '@/lib/ratesMonthlyAuto';

type RatesMonthlyAutoPanelProps = {
  state: MonthlyAutoSyncState;
  isSyncing: boolean;
  isMonthlySyncRunning: boolean;
  onToggleEnabled: (enabled: boolean) => void;
  onRunMonthly: () => void;
  onRestartMonthly: () => void;
};

export function RatesMonthlyAutoPanel({
  state,
  isSyncing,
  isMonthlySyncRunning,
  onToggleEnabled,
  onRunMonthly,
  onRestartMonthly,
}: RatesMonthlyAutoPanelProps) {
  const showRunMonthly =
    state.enabled && state.isFirstDayOfMonth && !state.completedThisMonth && !isSyncing;
  const showRestart =
    state.enabled && state.isFirstDayOfMonth && state.completedThisMonth && !isSyncing;

  return (
    <div className="flex flex-col gap-3 rounded-lg border bg-muted/20 px-4 py-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3 min-w-0">
          <CalendarClock className="h-4 w-4 shrink-0 text-muted-foreground" />
          <div className="min-w-0">
            <Label htmlFor="rates-monthly-auto" className="font-medium cursor-pointer">
              Mise à jour automatique le 1er du mois
            </Label>
            <p className="text-xs text-muted-foreground mt-0.5">{state.statusLabel}</p>
          </div>
        </div>
        <Switch
          id="rates-monthly-auto"
          checked={state.enabled}
          onCheckedChange={onToggleEnabled}
          disabled={isMonthlySyncRunning}
        />
      </div>

      {(showRunMonthly || showRestart) && (
        <div className="flex flex-wrap gap-2 border-t border-border/60 pt-3">
          {showRunMonthly && (
            <Button type="button" variant="secondary" size="sm" onClick={onRunMonthly}>
              <Play className="mr-2 h-3.5 w-3.5" />
              Lancer la mise à jour du mois
            </Button>
          )}
          {showRestart && (
            <Button type="button" variant="outline" size="sm" onClick={onRestartMonthly}>
              <RotateCcw className="mr-2 h-3.5 w-3.5" />
              Recommencer la mise à jour du mois
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
