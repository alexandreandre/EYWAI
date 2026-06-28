import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { DsnCoverageMatrix } from '@/features/dsn-import/components/DsnCoverageMatrix';
import { DsnImportHistory } from '@/features/dsn-import/components/DsnImportHistory';
import { DsnImportQuickStrip } from '@/features/dsn-import/components/DsnImportQuickStrip';
import { DsnImportSheet } from '@/features/dsn-import/components/DsnImportSheet';
import { DsnPeriodActionDialog } from '@/features/dsn-import/components/DsnPeriodActionDialog';
import { useDsnImportCommitWatcher } from '@/features/dsn-import/hooks/useDsnImportCommitWatcher';
import { PayrollExportImportPanel } from '@/features/admin-import/components/PayrollExportImportPanel';
import { CpImportPanel } from '@/features/admin-import/components/CpImportPanel';
import { CompanySetupHub } from '@/features/admin-import/components/CompanySetupHub';
import {
  CompanySetupStepHeading,
  CompanySetupStepNav,
} from '@/features/admin-import/components/CompanySetupStepNav';
import {
  CompanySetupContentShell,
  CompanySetupPickCompanyHint,
} from '@/features/admin-import/components/CompanySetupContentShell';
import { SeniorityImportPanel } from '@/features/admin-import/components/SeniorityImportPanel';
import { CompanySetupWizard } from '@/features/admin-import/components/CompanySetupWizard';
import { CompanySetupParamsStep } from '@/features/admin-import/components/CompanySetupParamsStep';
import { PlanningImportPanel } from '@/features/admin-import/components/PlanningImportPanel';
import {
  CompanyImportProvider,
  useCompanyImport,
} from '@/features/admin-import/context/CompanyImportContext';
import type { CompanySetupTab } from '@/features/admin-import/lib/companySetupSteps';
import type { DsnImportLaunchConfig, DsnImportMode } from '@/api/dsnImport';
import { invalidateDsnCoverageForCompany } from '@/lib/dsnCoverageCache';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = [CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1];

function DsnImportPageContent() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const {
    companyId,
    setCompanyId,
    activeTab,
    setActiveTab,
    openWizard,
  } = useCompanyImport();
  const [year, setYear] = useState(CURRENT_YEAR);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [launchConfig, setLaunchConfig] = useState<DsnImportLaunchConfig | null>(null);
  const [initialFiles, setInitialFiles] = useState<File[] | undefined>();
  const [sessionKey, setSessionKey] = useState<string | null>(null);
  const [periodAction, setPeriodAction] = useState<{
    companyId: string;
    companyName?: string | null;
    period: string;
  } | null>(null);
  const [committingBatchId, setCommittingBatchId] = useState<string | null>(null);

  useDsnImportCommitWatcher(committingBatchId, {
    enabled: !sheetOpen,
    onFinished: () => setCommittingBatchId(null),
  });

  const handleCommitStarted = useCallback((batchId: string) => {
    setCommittingBatchId(batchId);
  }, []);

  const openSheet = useCallback((config: DsnImportLaunchConfig, files?: File[]) => {
    setSessionKey(crypto.randomUUID());
    setLaunchConfig(config);
    setInitialFiles(files);
    setSheetOpen(true);
  }, []);

  const handleSheetClose = useCallback(() => {
    setSheetOpen(false);
    setLaunchConfig(null);
    setInitialFiles(undefined);
    void queryClient.refetchQueries({ queryKey: ['dsn-admin-matrix'] });
    void queryClient.refetchQueries({ queryKey: ['dsn-admin-late-summary'] });
    void queryClient.refetchQueries({ queryKey: ['dsn-import-batches'] });
    if (companyId) {
      void queryClient.invalidateQueries({ queryKey: ['company-setup-status', companyId] });
    }
    void queryClient.invalidateQueries({ queryKey: ['dsn-coverage'] });
  }, [queryClient, companyId]);

  const handleContinueOnboarding = useCallback(
    (targetCompanyId: string) => {
      setCompanyId(targetCompanyId);
      setSheetOpen(false);
      setLaunchConfig(null);
      setInitialFiles(undefined);
      openWizard('payroll-export');
    },
    [setCompanyId, openWizard],
  );

  const handleHistoryResume = useCallback(
    (batch: { id: string; summary?: Record<string, unknown> }) => {
      openSheet({
        mode: (batch.summary?.import_mode as DsnImportMode) || 'onboarding',
        targetCompanyId: (batch.summary?.target_company_id as string) ?? null,
        resumeBatchId: batch.id,
      });
    },
    [openSheet],
  );

  useEffect(() => {
    const urlCompanyId = searchParams.get('companyId');
    const mode = searchParams.get('mode');
    if (urlCompanyId && mode === 'monthly' && !searchParams.get('wizard')) {
      setActiveTab('dsn');
      setCompanyId(urlCompanyId);
      openSheet({ mode: 'monthly', targetCompanyId: urlCompanyId });
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, openSheet, setSearchParams, setCompanyId, setActiveTab]);

  useEffect(() => {
    const resumeBatch = searchParams.get('resumeBatch');
    if (!resumeBatch) return;
    setActiveTab('dsn');
    openSheet({
      mode: 'monthly',
      resumeBatchId: resumeBatch,
    });
    setSearchParams({}, { replace: true });
  }, [searchParams, openSheet, setSearchParams, setActiveTab]);

  const handleStripAnalyze = useCallback(
    (files: File[], suggestedPeriod?: string | null) => {
      if (!companyId) return;
      openSheet(
        {
          mode: 'monthly',
          targetCompanyId: companyId,
          suggestedPeriod: suggestedPeriod ?? undefined,
        },
        files,
      );
    },
    [companyId, openSheet],
  );

  const handleCellClick = useCallback(
    (
      cellCompanyId: string,
      period: string,
      state: 'covered' | 'missing' | 'future' | 'preview',
      companyName?: string | null,
    ) => {
      setCompanyId(cellCompanyId);
      setActiveTab('dsn');
      if (state === 'covered') {
        setPeriodAction({ companyId: cellCompanyId, companyName, period });
        return;
      }
      openSheet({
        mode: 'monthly',
        targetCompanyId: cellCompanyId,
        suggestedPeriod: period,
        reimport: false,
      });
    },
    [openSheet, setCompanyId, setActiveTab],
  );

  const handlePeriodRevoked = useCallback(() => {
    if (periodAction?.companyId) {
      invalidateDsnCoverageForCompany(queryClient, periodAction.companyId);
      return;
    }
    void queryClient.invalidateQueries({ queryKey: ['dsn-admin-matrix'] });
    void queryClient.invalidateQueries({ queryKey: ['dsn-admin-late-summary'] });
    void queryClient.invalidateQueries({ queryKey: ['dsn-coverage'] });
  }, [queryClient, periodAction?.companyId]);

  const handleImportCompany = useCallback(
    (importCompanyId: string) => {
      setCompanyId(importCompanyId);
      setActiveTab('dsn');
      openSheet({
        mode: 'monthly',
        targetCompanyId: importCompanyId,
      });
    },
    [openSheet, setCompanyId, setActiveTab],
  );

  const yearSelector = useMemo(
    () => (
      <Select value={String(year)} onValueChange={(v) => setYear(parseInt(v, 10))}>
        <SelectTrigger className="h-8 w-[92px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {YEAR_OPTIONS.map((y) => (
            <SelectItem key={y} value={String(y)}>
              {y}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    ),
    [year],
  );

  const handleTabChange = useCallback(
    (tab: CompanySetupTab) => setActiveTab(tab),
    [setActiveTab],
  );

  const stepContent = () => {
    switch (activeTab) {
      case 'dsn':
        return (
          <div className="space-y-6">
            {companyId ? (
              <DsnImportQuickStrip
                selectedCompanyId={companyId}
                onCompanyChange={setCompanyId}
                onAnalyze={handleStripAnalyze}
                hideCompanySelector
              />
            ) : (
              <p className="text-sm text-muted-foreground rounded-lg border border-dashed p-4">
                Sélectionnez une entreprise pour importer un mois précis, ou parcourez la matrice
                ci-dessous pour toutes les filiales.
              </p>
            )}
            <div className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h3 className="text-sm font-semibold">Couverture DSN — groupe</h3>
                {yearSelector}
              </div>
              <DsnCoverageMatrix
                year={year}
                onCellClick={handleCellClick}
                onImportCompany={handleImportCompany}
              />
            </div>
            <DsnImportHistory onResume={handleHistoryResume} />
          </div>
        );
      case 'seniority':
        return companyId ? (
          <SeniorityImportPanel companyId={companyId} standalone />
        ) : (
          <CompanySetupPickCompanyHint />
        );
      case 'payroll-export':
        return (
          <PayrollExportImportPanel
            fixedCompanyId={companyId}
            hideCompanySelector={Boolean(companyId)}
            onCompanyChange={setCompanyId}
            embedded
            showContext
          />
        );
      case 'cp':
        return (
          <CpImportPanel
            embedded
            fixedCompanyId={companyId || undefined}
          />
        );
      case 'params':
        return companyId ? (
          <CompanySetupParamsStep companyId={companyId} />
        ) : (
          <CompanySetupPickCompanyHint />
        );
      case 'planning':
        return companyId ? (
          <PlanningImportPanel companyId={companyId} embedded />
        ) : (
          <CompanySetupPickCompanyHint />
        );
      default:
        return null;
    }
  };

  return (
    <div className="space-y-5 max-w-6xl">
      <AdminPageHeader
        title="Configuration entreprise"
        description="Parcours guidé pour paramétrer une filiale : imports, soldes et paramètres paie."
      />

      <CompanySetupHub
        onStartWizard={() => openWizard('intro')}
        onNewDsnFolder={() => openSheet({ mode: 'onboarding' })}
      />

      <CompanySetupStepNav
        companyId={companyId}
        activeTab={activeTab}
        onTabChange={handleTabChange}
      />

      {activeTab === 'dsn' ? (
        stepContent()
      ) : (
        <CompanySetupContentShell>
          <CompanySetupStepHeading activeTab={activeTab} />
          {stepContent()}
        </CompanySetupContentShell>
      )}

      <CompanySetupWizard
        onOpenDsnOnboarding={() => openSheet({ mode: 'onboarding' })}
        onOpenDsnForCompany={(id) =>
          openSheet({ mode: 'monthly', targetCompanyId: id })
        }
        onAnalyzeDsn={handleStripAnalyze}
        onDsnCellClick={handleCellClick}
      />

      <DsnImportSheet
        open={sheetOpen}
        onOpenChange={(open) => {
          if (!open) handleSheetClose();
          else setSheetOpen(true);
        }}
        launchConfig={launchConfig}
        initialFiles={initialFiles}
        sessionKey={sessionKey}
        onCommitStarted={handleCommitStarted}
        onContinueOnboarding={handleContinueOnboarding}
      />

      {periodAction && (
        <DsnPeriodActionDialog
          open
          onOpenChange={(open) => {
            if (!open) setPeriodAction(null);
          }}
          companyId={periodAction.companyId}
          companyName={periodAction.companyName}
          period={periodAction.period}
          onReimport={() => {
            openSheet({
              mode: 'monthly',
              targetCompanyId: periodAction.companyId,
              suggestedPeriod: periodAction.period,
              reimport: true,
            });
            setPeriodAction(null);
          }}
          onRevoked={handlePeriodRevoked}
        />
      )}
    </div>
  );
}

export default function DsnImport() {
  return (
    <CompanyImportProvider>
      <DsnImportPageContent />
    </CompanyImportProvider>
  );
}
