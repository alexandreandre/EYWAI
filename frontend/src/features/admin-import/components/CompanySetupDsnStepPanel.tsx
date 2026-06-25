import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import {
  fetchDsnCoverage,
  type DsnCoverage,
  type DsnCoverageMatrixCompany,
  type DsnCoverageTimelineMonth,
} from '@/api/dsnImport';
import { DsnImportQuickStrip } from '@/features/dsn-import/components/DsnImportQuickStrip';
import {
  CompanyCoverageRow,
  CoverageLegend,
} from '@/features/dsn-import/components/DsnCoverageMatrix';
import { TooltipProvider } from '@/components/ui/tooltip';

function toMatrixCompany(coverage: DsnCoverage, companyName: string): DsnCoverageMatrixCompany {
  return {
    company_id: coverage.company_id,
    company_name: companyName,
    dsn_sync_mode: coverage.dsn_sync_mode,
    status: coverage.status,
    expected_last_period: coverage.expected_last_period,
    last_period: coverage.last_period,
    last_import_at: coverage.last_import_at,
    gaps_count: coverage.gaps.length,
    months_covered: coverage.months_covered,
    timeline: coverage.timeline,
  };
}

type Props = {
  companyId: string;
  companyName: string;
  employeesEmpty: boolean;
  onAnalyze: (files: File[], suggestedPeriod?: string | null) => void;
  onCellClick?: (
    companyId: string,
    period: string,
    state: DsnCoverageTimelineMonth['state'],
    companyName?: string | null,
  ) => void;
};

export function CompanySetupDsnStepPanel({
  companyId,
  companyName,
  employeesEmpty,
  onAnalyze,
  onCellClick,
}: Props) {
  const { data: coverage, isLoading, isFetching } = useQuery({
    queryKey: ['dsn-coverage', companyId],
    queryFn: () => fetchDsnCoverage(companyId),
    enabled: Boolean(companyId),
    staleTime: 5_000,
    refetchOnWindowFocus: true,
  });

  const matrixCompany = useMemo(
    () => (coverage ? toMatrixCompany(coverage, companyName) : null),
    [coverage, companyName],
  );

  return (
    <div className="space-y-4">
      {employeesEmpty ? (
        <div className="rounded-lg border border-amber-200 bg-amber-50/80 p-4 text-sm text-amber-950">
          <p className="font-medium">Aucun salarié dans cette entreprise.</p>
          <p className="mt-1 text-amber-900/90">
            {(coverage?.months_covered.length ?? 0) > 0 ? (
              <>
                Réimportez une DSN pour recréer les effectifs. L&apos;historique d&apos;import est
                conservé, mais les salariés ont été supprimés.
              </>
            ) : (
              <>
                Importez la DSN de chaque mois jusqu&apos;au mois en cours pour créer les salariés,
                les cumuls et l&apos;historique de paie.
              </>
            )}
          </p>
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          Importez la DSN de chaque mois jusqu&apos;au mois en cours — même règle que la matrice
          groupe.
        </p>
      )}

      {isLoading ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground py-6">
          <Loader2 className="h-4 w-4 animate-spin" />
          Chargement de la couverture DSN…
        </div>
      ) : matrixCompany ? (
        <TooltipProvider delayDuration={200}>
          <div className="space-y-3">
            {isFetching && !isLoading ? (
              <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" aria-hidden />
                Actualisation de la couverture DSN…
              </p>
            ) : null}
            <CompanyCoverageRow
              company={matrixCompany}
              onCellClick={onCellClick}
              embedded
            />
            <CoverageLegend compact />
          </div>
        </TooltipProvider>
      ) : null}

      <DsnImportQuickStrip
        selectedCompanyId={companyId}
        onCompanyChange={() => {}}
        onAnalyze={onAnalyze}
        hideCompanySelector
        embedded
      />
    </div>
  );
}
