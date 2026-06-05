import { useEffect, useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog';
import { Button } from '@/components/ui/button';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Progress } from '@/components/ui/progress';
import type { RatesSyncStatusResponse } from '@/api/rates';
import {
  aggregateSyncProgress,
  collectSyncRateTargets,
  computeActiveSyncElapsedSec,
  displaySyncProgressPercent,
  formatSyncProgressEstimate,
  formatSyncProgressEstimateFromJobs,
  partitionSyncRateTargets,
  shouldPartitionSyncTargets,
  type SyncRateTarget,
} from '@/lib/ratesSyncProgress';
import {
  sumStoredSyncDurationForFullSync,
  sumStoredSyncDurationForTarget,
} from '@/lib/ratesSyncDurationStorage';
import type { RatesSyncTarget } from '@/lib/ratesSyncManifest';
import {
  buildSyncOutcomePresentation,
  humanizeSyncError,
} from '@/lib/ratesSyncOutcome';
import { cn } from '@/lib/utils';

type ActiveSyncView = {
  syncId: string;
  label: string;
  target: RatesSyncTarget;
  status: RatesSyncStatusResponse | null;
  isMonthly?: boolean;
};

type RatesSyncBannerProps = {
  isSyncing: boolean;
  syncError: string | null;
  syncOutcome: RatesSyncStatusResponse | null;
  activeSyncs: ActiveSyncView[];
  onCancelSync?: (syncId: string) => void;
  onCancelAll?: () => void;
  onDismissOutcome?: () => void;
};

function RateTargetChip({
  target,
  muted = false,
}: {
  target: SyncRateTarget;
  muted?: boolean;
}) {
  return (
    <span
      className={cn(
        'inline-flex h-7 items-center gap-1.5 rounded-md border px-2.5 text-xs font-medium',
        muted && 'border-border/50 bg-muted/20 text-muted-foreground/80',
        !muted && 'border-border/80 bg-muted/40 text-muted-foreground',
        !muted && target.status === 'running' && 'text-foreground',
        target.status === 'failed' &&
          'border-destructive/30 bg-destructive/[0.04] text-destructive/90',
      )}
    >
      {target.status === 'running' ? (
        <span className="h-1 w-3 shrink-0 rounded-full bg-current animate-pulse" aria-hidden />
      ) : target.status === 'done' ? (
        <CheckCircle2
          className={cn('h-3 w-3', muted ? 'text-muted-foreground/60' : 'text-emerald-600/80')}
          aria-hidden
        />
      ) : target.status === 'failed' ? (
        <XCircle className="h-3 w-3 shrink-0 text-destructive/80" aria-hidden />
      ) : (
        <span className="h-1.5 w-1.5 rounded-full bg-current opacity-50" aria-hidden />
      )}
      <span className="truncate max-w-[14rem]">{target.label}</span>
    </span>
  );
}

const MAX_VISIBLE_CHIPS = 8;

function SyncTargetChipSection({
  label,
  targets,
  muted = false,
}: {
  label: string;
  targets: SyncRateTarget[];
  muted?: boolean;
}) {
  if (targets.length === 0) return null;

  const visible = targets.slice(0, MAX_VISIBLE_CHIPS);
  const hiddenCount = targets.length - visible.length;

  return (
    <div className="space-y-1.5">
      <p className="text-xs font-medium text-muted-foreground">
        {label}
        <span className="ml-1.5 font-normal tabular-nums">({targets.length})</span>
      </p>
      <div className="flex flex-wrap gap-1.5">
        {visible.map((target) => (
          <RateTargetChip key={target.label} target={target} muted={muted} />
        ))}
        {hiddenCount > 0 && (
          <span className="inline-flex h-7 items-center rounded-md border border-border/80 bg-muted/40 px-2.5 text-xs font-medium text-muted-foreground">
            +{hiddenCount} autre{hiddenCount > 1 ? 's' : ''}
          </span>
        )}
      </div>
    </div>
  );
}

function SyncProgressTargets({
  statuses,
  totalJobs,
  syncScopes,
}: {
  statuses: Array<RatesSyncStatusResponse | null>;
  totalJobs: number;
  syncScopes: Array<RatesSyncTarget['scope']>;
}) {
  const targets = collectSyncRateTargets(statuses);
  if (targets.length === 0) return null;

  const isMultiStep = shouldPartitionSyncTargets(totalJobs, targets.length, syncScopes);
  if (!isMultiStep) {
    return (
      <div className="flex flex-wrap gap-1.5">
        {targets.map((target) => (
          <RateTargetChip key={target.label} target={target} />
        ))}
      </div>
    );
  }

  const { remaining, completed, failed } = partitionSyncRateTargets(statuses);
  const processed = [...completed, ...failed];

  return (
    <div className="space-y-3">
      <SyncTargetChipSection label="Restants" targets={remaining} />
      <SyncTargetChipSection label="Traités" targets={processed} muted />
    </div>
  );
}

function resolveLastKnownDurationSec(activeSyncs: ActiveSyncView[]): number | null {
  let maxSec = 0;
  let found = false;

  for (const sync of activeSyncs) {
    const sectionEstimate =
      sync.target.scope === 'all'
        ? sumStoredSyncDurationForFullSync()
        : sumStoredSyncDurationForTarget(sync.target);
    if (sectionEstimate != null) {
      maxSec = Math.max(maxSec, sectionEstimate);
      found = true;
    }
  }

  return found ? maxSec : null;
}

function buildSummaryLine(
  awaitingStatus: boolean,
  agg: ReturnType<typeof aggregateSyncProgress>,
  estimateLine: string | null,
): string {
  if (awaitingStatus) {
    return 'Préparation de la mise à jour…';
  }

  const parts: string[] = [];

  if (agg.totalJobs > 1) {
    parts.push(
      `${agg.doneJobs} sur ${agg.totalJobs} étape${agg.totalJobs > 1 ? 's' : ''} terminée${agg.doneJobs > 1 ? 's' : ''}`,
    );
  } else if (agg.totalJobs === 1 && agg.doneJobs === 0) {
    parts.push('Récupération des données officielles…');
  } else if (agg.totalJobs === 1 && agg.doneJobs === 1) {
    parts.push('Finalisation…');
  }

  if (agg.failedJobs > 0) {
    parts.push(`${agg.failedJobs} en échec — poursuite des autres`);
  }

  if (estimateLine) {
    parts.push(estimateLine);
  }

  return parts.length > 0 ? parts.join(' · ') : 'Mise à jour des taux en cours…';
}

function SyncLogsPanel({ jobs }: { jobs: RatesSyncStatusResponse['jobs'] }) {
  if (jobs.length === 0) return null;

  return (
    <Accordion type="multiple" className="w-full">
      {jobs.map((job) => {
        const logs = job.execution_logs ?? [];
        if (logs.length === 0) return null;
        return (
          <AccordionItem key={job.job_id ?? job.source_key} value={job.source_key} className="border-border/60">
            <AccordionTrigger className="py-2 text-xs font-medium hover:no-underline">
              Journal — {job.source_name}
              <span className="ml-2 font-normal text-muted-foreground">
                ({logs.length} ligne{logs.length > 1 ? 's' : ''})
              </span>
            </AccordionTrigger>
            <AccordionContent>
              <pre className="max-h-48 overflow-auto rounded-md border border-border/60 bg-muted/30 p-3 text-[11px] leading-relaxed text-foreground/90 whitespace-pre-wrap break-words">
                {logs.join('\n')}
              </pre>
            </AccordionContent>
          </AccordionItem>
        );
      })}
    </Accordion>
  );
}

function SyncOutcomeBanner({
  outcome,
  onDismiss,
}: {
  outcome: RatesSyncStatusResponse;
  onDismiss?: () => void;
}) {
  const presentation = buildSyncOutcomePresentation(outcome);
  const Icon =
    presentation.tone === 'success'
      ? CheckCircle2
      : presentation.tone === 'warning'
        ? AlertTriangle
        : presentation.tone === 'error'
          ? AlertCircle
          : Info;

  const borderClass =
    presentation.tone === 'success'
      ? 'border-emerald-500/40 bg-emerald-500/5'
      : presentation.tone === 'warning'
        ? 'border-amber-500/40 bg-amber-500/5'
        : presentation.tone === 'error'
          ? 'border-destructive/50 bg-destructive/10'
          : 'border-border/80 bg-muted/30';

  const iconClass =
    presentation.tone === 'success'
      ? 'text-emerald-600'
      : presentation.tone === 'warning'
        ? 'text-amber-600'
        : presentation.tone === 'error'
          ? 'text-destructive'
          : 'text-muted-foreground';

  return (
    <div
      role="status"
      aria-live="polite"
      className={cn('rounded-lg border p-4', borderClass)}
    >
      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
          <div className="flex min-w-0 gap-3">
            <Icon className={cn('mt-0.5 h-5 w-5 shrink-0', iconClass)} aria-hidden />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">{presentation.title}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{presentation.summary}</p>
            </div>
          </div>
          {onDismiss && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="h-8 shrink-0 text-muted-foreground"
              onClick={onDismiss}
            >
              <X className="mr-1.5 h-3.5 w-3.5" />
              Fermer
            </Button>
          )}
        </div>

        {presentation.failedJobs.length > 0 && (
          <ul className="space-y-2 rounded-md border border-border/60 bg-background/60 p-3">
            {presentation.failedJobs.map((job) => (
              <li key={job.job_id ?? job.source_key} className="text-sm">
                <span className="font-medium text-foreground">{job.source_name}</span>
                <span className="text-muted-foreground"> — </span>
                <span className="text-muted-foreground">
                  {humanizeSyncError(job.error_message)}
                </span>
              </li>
            ))}
          </ul>
        )}

        {presentation.jobsWithLogs.length > 0 && (
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">
              Journal technique
              <span className="ml-1 font-normal">
                (pour diagnostic — copiez ces lignes en cas de problème)
              </span>
            </p>
            <SyncLogsPanel jobs={presentation.jobsWithLogs} />
          </div>
        )}
      </div>
    </div>
  );
}

export function RatesSyncBanner({
  isSyncing,
  syncError,
  syncOutcome,
  activeSyncs,
  onCancelAll,
  onDismissOutcome,
}: RatesSyncBannerProps) {
  const [cancelDialogOpen, setCancelDialogOpen] = useState(false);
  const [, setProgressTick] = useState(0);

  useEffect(() => {
    if (!isSyncing) return;
    const id = window.setInterval(() => setProgressTick((n) => n + 1), 1000);
    return () => window.clearInterval(id);
  }, [isSyncing]);

  const handleConfirmCancel = () => {
    setCancelDialogOpen(false);
    onCancelAll?.();
  };

  if (syncError) {
    return (
      <div
        role="alert"
        className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-destructive"
      >
        <div className="flex gap-3">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <div>
            <p className="font-medium">Échec de la mise à jour</p>
            <p className="mt-1 text-sm">{syncError}</p>
          </div>
        </div>
      </div>
    );
  }

  if (isSyncing) {
    if (activeSyncs.length === 0) {
      return (
        <div
          role="status"
          aria-live="polite"
          className="sticky top-2 z-30 rounded-lg border border-border/80 bg-card p-4 shadow-sm"
        >
          <div className="flex flex-col gap-3">
            <div>
              <p className="text-sm font-semibold">Mise à jour en cours</p>
              <p className="text-xs text-muted-foreground">Reprise de la mise à jour…</p>
            </div>
            <Progress value={12} className="h-3 w-full bg-muted" />
          </div>
        </div>
      );
    }

    const statuses = activeSyncs.map((s) => s.status);
    const awaitingStatus = statuses.every((s) => !s);
    const agg = aggregateSyncProgress(statuses);
    const allJobs = statuses.flatMap((s) => s?.jobs ?? []);
    const elapsedSec = computeActiveSyncElapsedSec(statuses);
    const lastKnownSec = resolveLastKnownDurationSec(activeSyncs);
    const estimateLine =
      allJobs.length > 0
        ? formatSyncProgressEstimateFromJobs(allJobs, elapsedSec)
        : formatSyncProgressEstimate(elapsedSec, lastKnownSec);
    const barPercent = displaySyncProgressPercent(agg, true, {
      elapsedSec,
      referenceSec: lastKnownSec,
      awaitingStatus,
      jobs: allJobs,
    });
    const hasTargetChips = collectSyncRateTargets(statuses).length > 0;

    const isMonthly = activeSyncs.some((s) => s.isMonthly);
    const title = isMonthly ? 'Mise à jour automatique du mois en cours' : 'Mise à jour en cours';
    const summaryLine = buildSummaryLine(awaitingStatus, agg, estimateLine);

    return (
      <div
        role="status"
        aria-live="polite"
        className="sticky top-2 z-30 rounded-lg border border-border/80 bg-card p-4 shadow-sm"
      >
        <div className="flex flex-col gap-3">
          <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">{title}</p>
              <p className="text-xs text-muted-foreground">{summaryLine}</p>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xl font-semibold tabular-nums text-foreground">
                {awaitingStatus ? '…' : `${barPercent} %`}
              </span>
              {onCancelAll && (
                <>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="h-8 shrink-0"
                    onClick={() => setCancelDialogOpen(true)}
                  >
                    <X className="mr-1.5 h-3.5 w-3.5" />
                    {activeSyncs.length > 1 ? 'Tout arrêter' : 'Arrêter'}
                  </Button>
                  <AlertDialog open={cancelDialogOpen} onOpenChange={setCancelDialogOpen}>
                    <AlertDialogContent>
                      <AlertDialogHeader>
                        <AlertDialogTitle>Êtes-vous sûr ?</AlertDialogTitle>
                        <AlertDialogDescription>
                          La synchronisation sera interrompue immédiatement.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel>Non</AlertDialogCancel>
                        <AlertDialogAction onClick={handleConfirmCancel}>
                          Oui, arrêter
                        </AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </>
              )}
            </div>
          </div>

          <Progress value={barPercent} className="h-3 w-full bg-muted" />

          {hasTargetChips && (
            <SyncProgressTargets
              statuses={statuses}
              totalJobs={agg.totalJobs}
              syncScopes={activeSyncs.map((s) => s.target.scope)}
            />
          )}
        </div>
      </div>
    );
  }

  if (syncOutcome) {
    return (
      <SyncOutcomeBanner outcome={syncOutcome} onDismiss={onDismissOutcome} />
    );
  }

  return null;
}
