import { Check } from 'lucide-react';
import { useCompanySetupStatus } from '@/features/admin-import/hooks/useCompanySetupStatus';
import {
  COMPANY_SETUP_STEPS,
  getCompanySetupStepState,
  type CompanySetupTab,
} from '@/features/admin-import/lib/companySetupSteps';
import { cn } from '@/lib/utils';

type Props = {
  companyId: string;
  activeTab: string;
  onTabChange: (tab: CompanySetupTab) => void;
};

export function CompanySetupStepNav({ companyId, activeTab, onTabChange }: Props) {
  const { data: status } = useCompanySetupStatus(companyId);

  return (
    <nav
      className="overflow-x-auto rounded-xl border bg-muted/20 p-1.5 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      aria-label="Étapes de configuration"
    >
      <div className="flex min-w-0 gap-1">
      {COMPANY_SETUP_STEPS.map((step, index) => {
        const stepState = getCompanySetupStepState(step.id, status);
        const done = Boolean(companyId) && stepState === 'done';
        const blocked = Boolean(companyId) && stepState === 'blocked';
        const active = activeTab === step.tab;
        return (
          <button
            key={step.id}
            type="button"
            onClick={() => onTabChange(step.tab)}
            className={cn(
              'flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
              active
                ? 'bg-background shadow-sm font-medium text-foreground ring-1 ring-border'
                : 'text-muted-foreground hover:bg-background/60 hover:text-foreground',
            )}
          >
            <span
              className={cn(
                'flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
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
            <span className="truncate">{step.shortLabel}</span>
          </button>
        );
      })}
      </div>
    </nav>
  );
}

export function CompanySetupStepHeading({ activeTab }: { activeTab: string }) {
  const step = COMPANY_SETUP_STEPS.find((s) => s.tab === activeTab);
  if (!step) return null;
  return (
    <div className="mb-5 border-b pb-4">
      <h2 className="text-lg font-semibold tracking-tight">{step.label}</h2>
      <p className="mt-1 text-sm text-muted-foreground">{step.description}</p>
    </div>
  );
}
