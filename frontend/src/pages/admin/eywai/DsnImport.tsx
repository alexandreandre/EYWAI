import { useCallback, useEffect, useMemo, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { FolderPlus } from 'lucide-react';
import { AdminPageHeader } from '@/features/admin/components/eywai/AdminPageHeader';
import { DsnCoverageMatrix } from '@/features/dsn-import/components/DsnCoverageMatrix';
import { DsnImportHistory } from '@/features/dsn-import/components/DsnImportHistory';
import { DsnImportQuickStrip } from '@/features/dsn-import/components/DsnImportQuickStrip';
import { DsnImportSheet } from '@/features/dsn-import/components/DsnImportSheet';
import { DsnPeriodActionDialog } from '@/features/dsn-import/components/DsnPeriodActionDialog';
import { RibImportPanel } from '@/features/admin-import/components/RibImportPanel';
import type { DsnImportLaunchConfig, DsnImportMode } from '@/api/dsnImport';
import { Button } from '@/components/ui/button';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const CURRENT_YEAR = new Date().getFullYear();
const YEAR_OPTIONS = [CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1];

export default function DsnImport() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [activeTab, setActiveTab] = useState('dsn');
  const [year, setYear] = useState(CURRENT_YEAR);
  const [stripCompanyId, setStripCompanyId] = useState('');
  const [sheetOpen, setSheetOpen] = useState(false);
  const [launchConfig, setLaunchConfig] = useState<DsnImportLaunchConfig | null>(null);
  const [initialFiles, setInitialFiles] = useState<File[] | undefined>();
  const [sessionKey, setSessionKey] = useState<string | null>(null);
  const [periodAction, setPeriodAction] = useState<{
    companyId: string;
    companyName?: string | null;
    period: string;
  } | null>(null);

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
    void queryClient.invalidateQueries({ queryKey: ['dsn-admin-matrix'] });
    void queryClient.invalidateQueries({ queryKey: ['dsn-admin-late-summary'] });
    void queryClient.invalidateQueries({ queryKey: ['dsn-import-batches'] });
  }, [queryClient]);

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
    const companyId = searchParams.get('companyId');
    const mode = searchParams.get('mode');
    if (companyId && mode === 'monthly') {
      setActiveTab('dsn');
      setStripCompanyId(companyId);
      openSheet({ mode: 'monthly', targetCompanyId: companyId });
      setSearchParams({}, { replace: true });
    }
  }, [searchParams, openSheet, setSearchParams]);

  useEffect(() => {
    const resumeBatch = searchParams.get('resumeBatch');
    if (!resumeBatch) return;
    setActiveTab('dsn');
    openSheet({
      mode: 'monthly',
      resumeBatchId: resumeBatch,
    });
    setSearchParams({}, { replace: true });
  }, [searchParams, openSheet, setSearchParams]);

  const handleStripAnalyze = useCallback(
    (files: File[]) => {
      if (!stripCompanyId) return;
      openSheet(
        {
          mode: 'monthly',
          targetCompanyId: stripCompanyId,
        },
        files,
      );
    },
    [stripCompanyId, openSheet],
  );

  const handleCellClick = useCallback(
    (
      companyId: string,
      period: string,
      state: 'covered' | 'missing' | 'future' | 'preview',
      companyName?: string | null,
    ) => {
      setStripCompanyId(companyId);
      if (state === 'covered') {
        setPeriodAction({ companyId, companyName, period });
        return;
      }
      openSheet({
        mode: 'monthly',
        targetCompanyId: companyId,
        suggestedPeriod: period,
        reimport: false,
      });
    },
    [openSheet],
  );

  const handlePeriodRevoked = useCallback(() => {
    void queryClient.invalidateQueries({ queryKey: ['dsn-admin-matrix'] });
    void queryClient.invalidateQueries({ queryKey: ['dsn-admin-late-summary'] });
  }, [queryClient]);

  const handleImportCompany = useCallback(
    (companyId: string) => {
      setStripCompanyId(companyId);
      openSheet({
        mode: 'monthly',
        targetCompanyId: companyId,
      });
    },
    [openSheet],
  );

  const yearSelector = useMemo(
    () => (
      <Select value={String(year)} onValueChange={(v) => setYear(parseInt(v, 10))}>
        <SelectTrigger className="h-9 w-[100px]">
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

  return (
    <div className="space-y-4">
      <AdminPageHeader
        title="Import"
        description="Import DSN mensuelle par entreprise et import RIB salariés depuis Excel."
      />

      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList>
          <TabsTrigger value="dsn">Import DSN</TabsTrigger>
          <TabsTrigger value="rib">Import RIB</TabsTrigger>
        </TabsList>

        <TabsContent value="dsn" className="mt-4 space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              Vue mensuelle par entreprise — case verte = DSN importée, ambre = mois manquant.
            </p>
            <div className="flex items-center gap-2">
              {yearSelector}
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => openSheet({ mode: 'onboarding' })}
              >
                <FolderPlus className="mr-1.5 h-4 w-4" />
                Nouveau dossier (onboarding)
              </Button>
            </div>
          </div>

          <DsnImportQuickStrip
            selectedCompanyId={stripCompanyId}
            onCompanyChange={setStripCompanyId}
            onAnalyze={handleStripAnalyze}
          />

          <DsnCoverageMatrix
            year={year}
            onCellClick={handleCellClick}
            onImportCompany={handleImportCompany}
          />

          <DsnImportHistory onResume={handleHistoryResume} />
        </TabsContent>

        <TabsContent value="rib" className="mt-4">
          <RibImportPanel />
        </TabsContent>
      </Tabs>

      <DsnImportSheet
        open={sheetOpen}
        onOpenChange={(open) => {
          if (!open) handleSheetClose();
          else setSheetOpen(true);
        }}
        launchConfig={launchConfig}
        initialFiles={initialFiles}
        sessionKey={sessionKey}
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
