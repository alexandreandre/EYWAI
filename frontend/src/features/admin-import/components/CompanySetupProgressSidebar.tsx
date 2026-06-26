import { Check, Loader2 } from 'lucide-react';
import type { CompanySetupStatus } from '@/api/adminImport';
import {
  COMPANY_SETUP_STEPS,
  getCompanySetupStepState,
} from '@/features/admin-import/lib/companySetupSteps';
import { isSetupStepValidated } from '@/features/admin-import/lib/companySetupValidatedSteps';
import {
  scopedCompanySetupStatus,
  useCompanySetupStatus,
} from '@/features/admin-import/hooks/useCompanySetupStatus';
import { cn } from '@/lib/utils';

const WIZARD_STEPS = [
  { id: 'intro', label: 'Préparation' },
  ...COMPANY_SETUP_STEPS.map((s) => ({ id: s.id, label: s.label })),
  { id: 'summary', label: 'Bilan' },
];

type Props = {
  companyId: string;
  currentStep: string;
  status?: CompanySetupStatus;
  /** Étapes validées explicitement via « Valider l'étape » (persistées par filiale). */
  validatedSteps?: ReadonlySet<string>;
  isFetching?: boolean;
  onStepClick?: (stepId: string) => void;
  className?: string;
};

export function CompanySetupProgressSidebar({
  companyId,
  currentStep,
  status: statusProp,
  validatedSteps,
  isFetching = false,
  onStepClick,
  className,
}: Props) {
  const { data: fetchedStatus, isLoading } = useCompanySetupStatus(companyId, {
    enabled: Boolean(companyId) && !statusProp,
    refetchInterval: statusProp ? false : 30_000,
  });

  const status = scopedCompanySetupStatus(statusProp ?? fetchedStatus, companyId);
  const initialLoad = (isLoading && !status) || (Boolean(companyId) && !status && !statusProp);

  return (
    <aside className={cn('space-y-4', className)}>
      {status ? (
        <div className="rounded-lg border bg-muted/30 px-3 py-2">
          <p className="text-2xl font-bold tabular-nums">
            {status.overall_pct}%
            {isFetching ? (
              <Loader2 className="ml-1.5 inline h-3.5 w-3.5 animate-spin text-muted-foreground" />
            ) : null}
          </p>
          <p className="truncate text-xs text-muted-foreground">{status.company_name}</p>
        </div>
      ) : initialLoad ? (
        <div className="rounded-lg border bg-muted/30 px-3 py-2">
          <div className="h-8 w-16 animate-pulse rounded bg-muted" />
          <div className="mt-1 h-3 w-24 animate-pulse rounded bg-muted" />
        </div>
      ) : null}

      {initialLoad ? (
        <div className="space-y-1 px-1">
          {WIZARD_STEPS.map((step) => (
            <div key={step.id} className="h-9 animate-pulse rounded-md bg-muted/60" />
          ))}
        </div>
      ) : (
        <ol className="space-y-0.5">
          {WIZARD_STEPS.map((step, index) => {
            const done = isSetupStepValidated(step.id, companyId, validatedSteps ?? new Set());
            const blocked =
              step.id !== 'intro' &&
              step.id !== 'summary' &&
              getCompanySetupStepState(step.id, status) === 'blocked';
            const active = currentStep === step.id;
            return (
              <li key={step.id}>
                <button
                  type="button"
                  onClick={() => onStepClick?.(step.id)}
                  className={cn(
                    'flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left text-sm transition-colors',
                    active ? 'bg-primary/10 font-medium' : 'hover:bg-muted/80',
                  )}
                >
                  <span
                    className={cn(
                      'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-medium',
                      done
                        ? 'bg-emerald-100 text-emerald-800'
                        : blocked
                          ? 'bg-muted text-muted-foreground/70'
                          : active
                            ? 'bg-primary text-primary-foreground'
                            : 'bg-muted text-muted-foreground',
                    )}
                  >
                    {done ? <Check className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span className="truncate">{step.label}</span>
                </button>
              </li>
            );
          })}
        </ol>
      )}
    </aside>
  );
}

export { COMPANY_SETUP_STEPS as COMPANY_SETUP_STEPS_EXPORT };
