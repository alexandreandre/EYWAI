import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Inbox, RefreshCw } from 'lucide-react';
import { toast } from 'sonner';

import { useRatesQuery } from '@/hooks/queries/useRatesQuery';
import { useRatesSync } from '@/hooks/useRatesSync';
import { useRatesMonthlyAuto } from '@/hooks/useRatesMonthlyAuto';
import { TableSkeleton } from '@/components/skeletons/TableSkeleton';
import { RhPageHeader } from '@/components/layout';
import { PageFetchIndicator } from '@/components/skeletons/PageFetchIndicator';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { RatesSummaryBand } from '@/components/rates/RatesSummaryBand';
import { RatesSyncBanner } from '@/components/rates/RatesSyncBanner';
import { RatesPageToolbar } from '@/components/rates/RatesPageToolbar';
import { RatesKeyParamsSection } from '@/components/rates/RatesKeyParamsSection';
import { RatesCotisationsSection } from '@/components/rates/RatesCotisationsSection';
import { RatesBaremesSection } from '@/components/rates/RatesBaremesSection';
import { computeRatesSummary, getCategoryTitle, parseRatesError } from '@/lib/ratesUtils';
import type { RatesSyncTarget } from '@/lib/ratesSyncManifest';
import type { RatesResponse } from '@/api/rates';

function syncTargetLabel(target: RatesSyncTarget): string {
  switch (target.scope) {
    case 'all':
      return 'Mise à jour complète';
    case 'rate_key':
      return getCategoryTitle(target.rateKey);
    case 'source_key':
      return target.sourceKey;
    case 'cotisation_id':
      return target.cotisationId;
    default:
      return 'Mise à jour';
  }
}

function RatesErrorBlock({
  message,
  status,
  onRetry,
}: {
  message: string;
  status?: number;
  onRetry: () => void;
}) {
  const isEmpty = status === 404;

  return (
    <Alert variant={isEmpty ? 'default' : 'destructive'}>
      <AlertTitle>{isEmpty ? 'Référentiel vide' : 'Chargement impossible'}</AlertTitle>
      <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span>{message}</span>
        <Button variant="outline" size="sm" onClick={onRetry} className="shrink-0">
          <RefreshCw className="mr-2 h-4 w-4" />
          Réessayer
        </Button>
      </AlertDescription>
      {!isEmpty && (
        <Collapsible className="mt-3">
          <CollapsibleTrigger asChild>
            <Button variant="ghost" size="sm" className="h-auto p-0 text-xs">
              Détail technique
            </Button>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <p className="font-mono text-xs mt-2 p-2 rounded-md bg-muted">{message}</p>
          </CollapsibleContent>
        </Collapsible>
      )}
    </Alert>
  );
}

export default function Rates() {
  const ratesQuery = useRatesQuery();
  const data = ratesQuery.data as RatesResponse | undefined;
  const loading = ratesQuery.isLoading && !ratesQuery.data;

  const loadError = ratesQuery.error
    ? parseRatesError(ratesQuery.error)
    : null;

  const [highlightedKeys, setHighlightedKeys] = useState<Set<string>>(new Set());
  const [keySectionOpen, setKeySectionOpen] = useState(false);
  const [cotisationsSectionOpen, setCotisationsSectionOpen] = useState(false);
  const [baremesSectionOpen, setBaremesSectionOpen] = useState(false);
  const autoMonthlyStarted = useRef(false);

  const monthly = useRatesMonthlyAuto();

  const onSyncComplete = useCallback(
    (changedKeys: string[]) => {
      monthly.refresh();
      if (changedKeys.length === 0) return;
      setHighlightedKeys(new Set(changedKeys));
      window.setTimeout(() => setHighlightedKeys(new Set()), 8000);
    },
    [monthly],
  );

  const {
    startSync,
    cancelSync,
    isSyncing,
    isMonthlySyncRunning,
    isSourceRunning,
    isRateKeyRunning,
    isCotisationRunning,
    syncError,
    activeSyncs,
    manifest,
    clearSyncError,
  } = useRatesSync(onSyncComplete);

  const summary = useMemo(
    () => (data ? computeRatesSummary(data) : null),
    [data],
  );

  const activeSyncViews = useMemo(
    () =>
      activeSyncs.map((s) => ({
        syncId: s.syncId,
        label: syncTargetLabel(s.target),
        status: s.status,
        isMonthly: s.isMonthly,
      })),
    [activeSyncs],
  );

  const handleRefresh = useCallback(() => {
    void ratesQuery.refetch();
  }, [ratesQuery]);

  const handleFullSync = useCallback(() => {
    clearSyncError();
    void startSync({ scope: 'all' });
  }, [clearSyncError, startSync]);

  const handleMonthlySync = useCallback(() => {
    clearSyncError();
    void startSync({ scope: 'all' }, { monthly: true });
  }, [clearSyncError, startSync]);

  const handleRestartMonthly = useCallback(() => {
    monthly.resetCycle();
    clearSyncError();
    void startSync({ scope: 'all' }, { monthly: true });
  }, [clearSyncError, monthly, startSync]);

  const handleMonthlyToggle = useCallback(
    (enabled: boolean) => {
      if (enabled) {
        monthly.resume();
        toast.success('Mise à jour automatique activée — prochaine exécution le 1er du mois');
      } else {
        if (isMonthlySyncRunning) {
          activeSyncs
            .filter((s) => s.isMonthly)
            .forEach((s) => void cancelSync(s.syncId));
        }
        monthly.pause();
        toast.info('Mise à jour automatique désactivée');
      }
    },
    [activeSyncs, cancelSync, isMonthlySyncRunning, monthly],
  );

  const handleUpdateRateKey = useCallback(
    (rateKey: string) => {
      clearSyncError();
      void startSync({ scope: 'rate_key', rateKey });
    },
    [clearSyncError, startSync],
  );

  const handleUpdateSource = useCallback(
    (sourceKey: string) => {
      clearSyncError();
      void startSync({ scope: 'source_key', sourceKey });
    },
    [clearSyncError, startSync],
  );

  const handleUpdateCotisation = useCallback(
    (cotisationId: string) => {
      clearSyncError();
      void startSync({ scope: 'cotisation_id', cotisationId });
    },
    [clearSyncError, startSync],
  );

  // Auto uniquement le 1er du mois, si activé et pas encore fait ce mois-ci
  useEffect(() => {
    if (autoMonthlyStarted.current || loading || loadError || !data || isSyncing) return;
    if (!monthly.shouldAutoStart) return;

    autoMonthlyStarted.current = true;
    toast.info('Mise à jour automatique du 1er du mois…');
    void startSync({ scope: 'all' }, { monthly: true });
  }, [loading, loadError, data, isSyncing, monthly.shouldAutoStart, startSync]);

  const toolbar = (
    <RatesPageToolbar
      onRefresh={handleRefresh}
      onFullSync={handleFullSync}
      isFetching={ratesQuery.isFetching}
      isSyncing={isSyncing}
      isMonthlySyncRunning={isMonthlySyncRunning}
      monthlyState={monthly.state}
      onMonthlyToggle={handleMonthlyToggle}
      onRunMonthly={handleMonthlySync}
      onRestartMonthly={handleRestartMonthly}
    />
  );

  const header = (
    <RhPageHeader
      title="Suivi des Taux"
      description="Consultez les taux réglementaires et mettez à jour chaque bloc ou l’ensemble du référentiel."
      actions={toolbar}
    />
  );

  if (loading) {
    return (
      <div className="space-y-6">
        {header}
        <PageFetchIndicator isFetching={ratesQuery.isFetching} />
        <TableSkeleton rows={10} columns={3} />
      </div>
    );
  }

  if (loadError && !data) {
    return (
      <div className="space-y-6">
        {header}
        <RatesSyncBanner
          isSyncing={isSyncing}
          syncError={syncError}
          activeSyncs={activeSyncViews}
          onCancelSync={cancelSync}
        />
        <RatesErrorBlock
          message={loadError.message}
          status={loadError.status}
          onRetry={handleRefresh}
        />
      </div>
    );
  }

  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="space-y-6">
        {header}
        <div className="flex flex-col justify-center items-center h-40 text-muted-foreground border rounded-lg px-4 text-center">
          <Inbox className="h-10 w-10" />
          <span className="mt-4 text-lg font-medium">Aucune donnée de configuration</span>
          <span className="text-sm mt-2">
            Utilisez « Mise à jour complète » dans le panneau ci-dessus.
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8 animate-fade-in">
      {header}
      <PageFetchIndicator isFetching={ratesQuery.isFetching} />

      {summary && (
        <RatesSummaryBand
          categoryCount={summary.categoryCount}
          obsoleteCount={summary.obsoleteCount}
          oldestCheck={summary.oldestCheck}
          health={summary.health}
        />
      )}

      <RatesSyncBanner
        isSyncing={isSyncing}
        syncError={syncError}
        activeSyncs={activeSyncViews}
        onCancelSync={cancelSync}
      />

      <RatesKeyParamsSection
        data={data}
        open={keySectionOpen}
        onOpenChange={setKeySectionOpen}
        highlightedKeys={highlightedKeys}
        manifest={manifest}
        onUpdateRateKey={handleUpdateRateKey}
        isTargetRunning={isRateKeyRunning}
      />

      {data.cotisations && (
        <RatesCotisationsSection
          cotisations={data.cotisations}
          open={cotisationsSectionOpen}
          onOpenChange={setCotisationsSectionOpen}
          highlightedKeys={highlightedKeys}
          manifest={manifest}
          onUpdateSource={handleUpdateSource}
          onUpdateCotisation={handleUpdateCotisation}
          isSourceRunning={isSourceRunning}
          isCotisationRunning={isCotisationRunning}
        />
      )}

      <RatesBaremesSection
        data={data}
        open={baremesSectionOpen}
        onOpenChange={setBaremesSectionOpen}
        highlightedKeys={highlightedKeys}
        manifest={manifest}
        onUpdateRateKey={handleUpdateRateKey}
        onUpdateSource={handleUpdateSource}
        isTargetRunning={isRateKeyRunning}
        isSourceRunning={isSourceRunning}
      />
    </div>
  );
}
