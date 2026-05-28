import { AlertCircle, ChevronDown, ChevronRight, Loader2, X } from 'lucide-react';
import { useState } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import type { RatesSyncStatusResponse } from '@/api/rates';
import {
  formatSyncEta,
  jobProgressPercent,
  jobStatusLabel,
  syncProgressLabel,
} from '@/lib/ratesSyncProgress';
import { cn } from '@/lib/utils';

type ActiveSyncView = {
  syncId: string;
  label: string;
  status: RatesSyncStatusResponse | null;
  isMonthly?: boolean;
};

type RatesSyncBannerProps = {
  isSyncing: boolean;
  syncError: string | null;
  activeSyncs: ActiveSyncView[];
  onCancelSync?: (syncId: string) => void;
};

function SyncJobRow({
  sourceName,
  statusLabel,
  percent,
  lastLog,
  isActive,
}: {
  sourceName: string;
  statusLabel: string;
  percent: number;
  lastLog?: string;
  isActive: boolean;
}) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className={cn('truncate font-medium', isActive && 'text-foreground')}>
          {sourceName}
        </span>
        <span className="shrink-0 text-muted-foreground">{statusLabel}</span>
      </div>
      <Progress value={percent} className="h-1" />
      {isActive && lastLog ? (
        <p className="text-[11px] text-muted-foreground truncate font-mono">{lastLog}</p>
      ) : null}
    </div>
  );
}

export function RatesSyncBanner({
  isSyncing,
  syncError,
  activeSyncs,
  onCancelSync,
}: RatesSyncBannerProps) {
  const [detailsOpen, setDetailsOpen] = useState<Record<string, boolean>>({});

  if (syncError) {
    return (
      <Alert variant="destructive">
        <AlertCircle className="h-4 w-4" />
        <AlertTitle>Échec de la mise à jour</AlertTitle>
        <AlertDescription>{syncError}</AlertDescription>
      </Alert>
    );
  }

  if (!isSyncing || activeSyncs.length === 0) return null;

  return (
    <div className="space-y-2">
      {activeSyncs.map(({ syncId, label, status, isMonthly }) => {
        const progress = status?.progress;
        const failedJobs =
          status?.jobs.filter((j) => j.status === 'failed' || j.success === false) ?? [];
        const title = isMonthly ? 'Mise à jour du mois (1er)' : label;
        const percentValue = progress?.percent_exact ?? progress?.percent ?? 0;
        const eta = formatSyncEta(progress?.eta_seconds);
        const showDetails = detailsOpen[syncId] ?? true;
        const runningJobs = status?.jobs.filter((j) => j.status === 'running') ?? [];
        const pendingJobs = status?.jobs.filter((j) => j.status === 'pending') ?? [];
        const doneJobs =
          status?.jobs.filter(
            (j) =>
              j.status === 'completed' ||
              j.status === 'failed' ||
              j.status === 'cancelled',
          ) ?? [];

        return (
          <Alert key={syncId}>
            <Loader2 className="h-4 w-4 animate-spin" />
            <div className="flex flex-1 flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="flex-1 space-y-2 min-w-0">
                <AlertTitle>{title}</AlertTitle>
                <AlertDescription className="space-y-2">
                  {progress ? (
                    <>
                      <p className="text-sm font-medium text-foreground">
                        {syncProgressLabel(status)}
                      </p>
                      <div className="space-y-1">
                        <div className="flex justify-between text-xs text-muted-foreground">
                          <span>
                            {progress.done} / {progress.total} source
                            {progress.total > 1 ? 's' : ''}
                            {progress.running > 0
                              ? ` · ${progress.running} en cours`
                              : ''}
                            {(progress.pending ?? 0) > 0
                              ? ` · ${progress.pending} en attente`
                              : ''}
                          </span>
                          <span>{Math.round(percentValue)} %</span>
                        </div>
                        <Progress value={percentValue} className="h-2" />
                        {eta ? (
                          <p className="text-xs text-muted-foreground">{eta}</p>
                        ) : null}
                      </div>

                      {status?.jobs && status.jobs.length > 0 ? (
                        <Collapsible
                          open={showDetails}
                          onOpenChange={(open) =>
                            setDetailsOpen((prev) => ({ ...prev, [syncId]: open }))
                          }
                        >
                          <CollapsibleTrigger asChild>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-7 px-0 text-xs text-muted-foreground hover:text-foreground"
                            >
                              {showDetails ? (
                                <ChevronDown className="mr-1 h-3.5 w-3.5" />
                              ) : (
                                <ChevronRight className="mr-1 h-3.5 w-3.5" />
                              )}
                              Détail par source ({status.jobs.length})
                            </Button>
                          </CollapsibleTrigger>
                          <CollapsibleContent className="space-y-2 pt-1 max-h-48 overflow-y-auto">
                            {runningJobs.map((j) => (
                              <SyncJobRow
                                key={j.source_key}
                                sourceName={j.source_name}
                                statusLabel={jobStatusLabel(j)}
                                percent={jobProgressPercent(j)}
                                lastLog={j.last_log_line || j.current_step}
                                isActive
                              />
                            ))}
                            {pendingJobs.map((j) => (
                              <SyncJobRow
                                key={j.source_key}
                                sourceName={j.source_name}
                                statusLabel={jobStatusLabel(j)}
                                percent={jobProgressPercent(j)}
                                isActive={false}
                              />
                            ))}
                            {doneJobs.map((j) => (
                              <SyncJobRow
                                key={j.source_key}
                                sourceName={j.source_name}
                                statusLabel={jobStatusLabel(j)}
                                percent={100}
                                isActive={false}
                              />
                            ))}
                          </CollapsibleContent>
                        </Collapsible>
                      ) : null}
                    </>
                  ) : (
                    <p>Initialisation…</p>
                  )}
                  {failedJobs.length > 0 && (
                    <ul className="text-xs text-muted-foreground list-disc pl-4">
                      {failedJobs.slice(0, 3).map((j) => (
                        <li key={j.source_key}>
                          {j.source_name}
                          {j.error_message ? ` : ${j.error_message}` : ''}
                        </li>
                      ))}
                    </ul>
                  )}
                </AlertDescription>
              </div>
              {onCancelSync && (
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="shrink-0 h-8"
                  onClick={() => onCancelSync(syncId)}
                >
                  <X className="mr-1.5 h-3.5 w-3.5" />
                  Arrêter
                </Button>
              )}
            </div>
          </Alert>
        );
      })}
    </div>
  );
}
