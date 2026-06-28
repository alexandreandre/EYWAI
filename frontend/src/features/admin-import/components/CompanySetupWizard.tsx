import { useCallback, useEffect, useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { CompanySetupIntroStep } from '@/features/admin-import/components/CompanySetupIntroStep';
import { CompanySetupProgressSidebar } from '@/features/admin-import/components/CompanySetupProgressSidebar';
import { CompanySetupParamsStep } from '@/features/admin-import/components/CompanySetupParamsStep';
import { CompanySetupSummaryStep } from '@/features/admin-import/components/CompanySetupSummaryStep';
import { PayrollExportImportPanel } from '@/features/admin-import/components/PayrollExportImportPanel';
import { CpImportPanel } from '@/features/admin-import/components/CpImportPanel';
import { PlanningImportPanel } from '@/features/admin-import/components/PlanningImportPanel';
import { SeniorityImportPanel } from '@/features/admin-import/components/SeniorityImportPanel';
import { CompanySetupDsnStepPanel } from '@/features/admin-import/components/CompanySetupDsnStepPanel';
import { CompanySetupWizardFooter } from '@/features/admin-import/components/CompanySetupWizardFooter';
import { useCompanyImport } from '@/features/admin-import/context/CompanyImportContext';
import {
  useCompanySetupStatus,
  useRefreshCompanySetupStatus,
} from '@/features/admin-import/hooks/useCompanySetupStatus';
import { cn } from '@/lib/utils';
import {
  isSetupStepValidated,
  loadValidatedSetupSteps,
  saveValidatedSetupSteps,
} from '@/features/admin-import/lib/companySetupValidatedSteps';
import type { DsnCoverageTimelineMonth } from '@/api/dsnImport';

const WIZARD_STEP_ORDER = [
  'intro',
  'dsn',
  'seniority',
  'payroll-export',
  'cp',
  'params',
  'planning',
  'summary',
] as const;

type WizardStepId = (typeof WIZARD_STEP_ORDER)[number];

type Props = {
  onOpenDsnOnboarding: () => void;
  onOpenDsnForCompany: (companyId: string) => void;
  onAnalyzeDsn?: (files: File[], suggestedPeriod?: string | null) => void;
  onDsnCellClick?: (
    companyId: string,
    period: string,
    state: DsnCoverageTimelineMonth['state'],
    companyName?: string | null,
  ) => void;
};

export function CompanySetupWizard({
  onOpenDsnOnboarding,
  onOpenDsnForCompany,
  onAnalyzeDsn,
  onDsnCellClick,
}: Props) {
  const {
    companyId,
    setCompanyId,
    wizardOpen,
    closeWizard,
    wizardStep,
    setWizardStep,
    setActiveTab,
  } = useCompanyImport();

  const refreshStatus = useRefreshCompanySetupStatus();
  const { data: status, isLoading: statusLoading, isFetching: statusFetching } = useCompanySetupStatus(
    companyId,
    { enabled: Boolean(companyId) && wizardOpen },
  );

  const [visitedSteps, setVisitedSteps] = useState<Set<string>>(() => new Set(['intro']));
  const [validatedSteps, setValidatedSteps] = useState<Set<string>>(() => new Set());

  const persistValidatedSteps = useCallback(
    (steps: Set<string>) => {
      if (companyId) saveValidatedSetupSteps(companyId, steps);
    },
    [companyId],
  );

  const validateStep = useCallback(
    (step: string) => {
      if (step === 'intro') return;
      setValidatedSteps((prev) => {
        if (prev.has(step)) return prev;
        const next = new Set(prev);
        next.add(step);
        persistValidatedSteps(next);
        return next;
      });
    },
    [persistValidatedSteps],
  );

  const unvalidateStep = useCallback(
    (step: string) => {
      if (step === 'intro') return;
      setValidatedSteps((prev) => {
        if (!prev.has(step)) return prev;
        const next = new Set(prev);
        next.delete(step);
        persistValidatedSteps(next);
        return next;
      });
    },
    [persistValidatedSteps],
  );

  useEffect(() => {
    if (!wizardOpen) {
      setVisitedSteps(new Set(['intro']));
      return;
    }
    if (companyId) {
      setValidatedSteps(loadValidatedSetupSteps(companyId));
    } else {
      setValidatedSteps(new Set());
    }
  }, [wizardOpen, companyId]);

  useEffect(() => {
    if (!wizardOpen) return;
    setVisitedSteps((prev) => {
      if (prev.has(wizardStep)) return prev;
      const next = new Set(prev);
      next.add(wizardStep);
      return next;
    });
  }, [wizardOpen, wizardStep]);

  const employeesEmpty = Boolean(status) && status.blocks.employees.total === 0;

  const skipCp = employeesEmpty;
  const skipPlanning = employeesEmpty;

  const shouldSkipWizardStep = useCallback(
    (step: string) => {
      if (step === 'seniority' && employeesEmpty) return true;
      if (step === 'payroll-export' && employeesEmpty) return true;
      if (step === 'cp' && skipCp) return true;
      if (step === 'planning' && skipPlanning) return true;
      return false;
    },
    [employeesEmpty, skipCp, skipPlanning],
  );

  const goNext = useCallback(() => {
    const idx = WIZARD_STEP_ORDER.indexOf(wizardStep as WizardStepId);
    let nextIdx = idx + 1;
    while (nextIdx < WIZARD_STEP_ORDER.length) {
      const step = WIZARD_STEP_ORDER[nextIdx];
      if (shouldSkipWizardStep(step)) {
        nextIdx += 1;
        continue;
      }
      setWizardStep(step);
      return;
    }
    setWizardStep('summary');
  }, [wizardStep, setWizardStep, shouldSkipWizardStep]);

  const goBack = useCallback(() => {
    const idx = WIZARD_STEP_ORDER.indexOf(wizardStep as WizardStepId);
    if (idx <= 0) return;
    let prevIdx = idx - 1;
    while (prevIdx >= 0) {
      const step = WIZARD_STEP_ORDER[prevIdx];
      if (shouldSkipWizardStep(step)) {
        prevIdx -= 1;
        continue;
      }
      setWizardStep(step);
      return;
    }
  }, [wizardStep, setWizardStep, shouldSkipWizardStep]);

  const afterStepAction = useCallback(() => {
    refreshStatus(companyId);
    goNext();
  }, [refreshStatus, companyId, goNext]);

  const renderStep = (step: string) => {
    switch (step) {
      case 'intro':
        return (
          <CompanySetupIntroStep
            companyId={companyId}
            onCompanyChange={setCompanyId}
            onCreateNewViaDsn={() => {
              closeWizard();
              onOpenDsnOnboarding();
            }}
          />
        );
      case 'dsn':
        return companyId ? (
          <CompanySetupDsnStepPanel
            companyId={companyId}
            companyName={status?.company_name ?? 'Entreprise'}
            employeesEmpty={employeesEmpty}
            onAnalyze={(files) => onAnalyzeDsn?.(files)}
            onCellClick={onDsnCellClick}
          />
        ) : (
          <p className="text-sm text-muted-foreground">
            Sélectionnez une entreprise à l&apos;étape précédente.
          </p>
        );
      case 'seniority':
        return companyId ? (
          <SeniorityImportPanel companyId={companyId} onComplete={afterStepAction} standalone />
        ) : (
          <p className="text-sm text-muted-foreground">
            Sélectionnez une entreprise à l&apos;étape précédente.
          </p>
        );
      case 'payroll-export':
        return (
          <PayrollExportImportPanel
            fixedCompanyId={companyId}
            hideCompanySelector
            embedded
            showContext
            setupStatus={status}
            onComplete={afterStepAction}
          />
        );
      case 'cp':
        return (
          <CpImportPanel
            embedded
            fixedCompanyId={companyId}
            fixedCompanyName={status?.company_name}
            onComplete={afterStepAction}
          />
        );
      case 'params':
        return <CompanySetupParamsStep companyId={companyId} idcc={status?.idcc} />;
      case 'planning':
        return (
          <PlanningImportPanel companyId={companyId} embedded onComplete={afterStepAction} />
        );
      case 'summary':
        return (
          <CompanySetupSummaryStep
            companyId={companyId}
            validatedSteps={validatedSteps}
            onOpenTab={(tab) => {
              closeWizard();
              setActiveTab(tab);
            }}
            onGoToStep={setWizardStep}
          />
        );
      default:
        return null;
    }
  };

  return (
    <Dialog open={wizardOpen} onOpenChange={(open) => !open && closeWizard()}>
      <DialogContent className="flex h-[min(720px,92vh)] w-[min(72rem,calc(100vw-2rem))] max-w-none flex-col gap-0 overflow-hidden p-0 sm:rounded-lg">
        <DialogHeader className="shrink-0 border-b px-6 py-4 min-h-[5.75rem]">
          <DialogTitle className="flex items-center gap-2 line-clamp-1">
            {wizardStep === 'intro' ? 'Parcours guidé — filiale existante' : 'Parcours guidé'}
            {statusFetching && status ? (
              <span className="text-xs font-normal text-muted-foreground">· actualisation…</span>
            ) : null}
          </DialogTitle>
          <DialogDescription className="line-clamp-2 min-h-[2.5rem]">
            {wizardStep === 'intro'
              ? 'Sélectionnez une entreprise déjà dans EYWAI. La création d’une nouvelle filiale passe par un import DSN initial.'
              : status?.company_name
                ? `${status.company_name} — suivez les étapes dans l’ordre.`
                : 'Suivez les étapes dans l’ordre — vous pouvez passer une étape si elle est déjà couverte.'}
          </DialogDescription>
        </DialogHeader>
        <div className="grid min-h-0 flex-1 gap-0 overflow-hidden lg:grid-cols-[240px_minmax(0,1fr)]">
          <div className="min-h-0 overflow-y-auto border-b bg-muted/20 px-4 py-4 lg:border-b-0 lg:border-r">
            <CompanySetupProgressSidebar
              companyId={companyId}
              currentStep={wizardStep}
              status={status}
              validatedSteps={validatedSteps}
              isFetching={statusFetching}
              onStepClick={setWizardStep}
            />
          </div>
          <div className="flex min-h-0 min-w-0 flex-col overflow-hidden">
            <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
              {WIZARD_STEP_ORDER.map((step) =>
                visitedSteps.has(step) ? (
                  <div
                    key={step}
                    className={cn('h-full', wizardStep !== step && 'hidden')}
                    aria-hidden={wizardStep !== step}
                  >
                    {renderStep(step)}
                  </div>
                ) : null,
              )}
            </div>
            <div className="shrink-0">
              {wizardStep === 'summary' ? (
                <div className="flex shrink-0 items-center justify-between gap-2 border-t bg-background px-4 py-2">
                  <Button type="button" variant="ghost" size="sm" className="h-8 px-2" onClick={goBack}>
                    Retour
                  </Button>
                  <Button type="button" size="sm" className="h-8 shrink-0" onClick={closeWizard}>
                    Fermer le parcours
                  </Button>
                </div>
              ) : (
                <CompanySetupWizardFooter
                  wizardStep={wizardStep}
                  companyId={companyId}
                  status={status}
                  statusLoading={statusLoading && !status}
                  isStepValidated={isSetupStepValidated(wizardStep, companyId, validatedSteps)}
                  showBack={wizardStep !== 'intro'}
                  onBack={goBack}
                  onNext={goNext}
                  onValidate={() => validateStep(wizardStep)}
                  onUnvalidate={() => unvalidateStep(wizardStep)}
                  onClose={wizardStep === 'intro' ? closeWizard : undefined}
                />
              )}
            </div>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
