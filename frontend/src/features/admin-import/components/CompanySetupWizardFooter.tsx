import { Check } from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { CompanySetupStatus } from '@/api/adminImport';
import {
  getCompanySetupStepState,
  isCompanySetupStepBlocked,
} from '@/features/admin-import/lib/companySetupSteps';
import { isSetupStepManuallyValidatable } from '@/features/admin-import/lib/companySetupValidatedSteps';

type Props = {
  wizardStep: string;
  companyId: string;
  status: CompanySetupStatus | undefined;
  statusLoading: boolean;
  isStepValidated: boolean;
  showBack?: boolean;
  onBack: () => void;
  onNext: () => void;
  onValidate: () => void;
  onUnvalidate: () => void;
  onClose?: () => void;
};

/** Étapes que l'on peut quitter sans avoir tout complété. */
const SKIPPABLE_INCOMPLETE = new Set(['payroll-export', 'cp', 'params', 'planning']);

function canAdvance(
  step: string,
  companyId: string,
  status: CompanySetupStatus | undefined,
  statusLoading: boolean,
): boolean {
  if (statusLoading) return false;
  if (step === 'intro') return Boolean(companyId);
  if (!companyId) return false;
  if (isCompanySetupStepBlocked(step, status)) return false;

  if (step === 'dsn') {
    if (!status) return false;
    return status.blocks.employees.total > 0 || status.blocks.dsn.complete;
  }

  return true;
}

function canValidate(
  step: string,
  companyId: string,
  status: CompanySetupStatus | undefined,
  statusLoading: boolean,
): boolean {
  if (statusLoading) return false;
  if (step === 'intro') return Boolean(companyId);
  if (!companyId) return false;
  return !isCompanySetupStepBlocked(step, status);
}

function canSkipIncomplete(
  step: string,
  companyId: string,
  status: CompanySetupStatus | undefined,
  statusLoading: boolean,
): boolean {
  if (statusLoading || !companyId || !status) return false;
  if (!SKIPPABLE_INCOMPLETE.has(step)) return false;
  if (isCompanySetupStepBlocked(step, status)) return false;
  if (getCompanySetupStepState(step, status) === 'done') return false;
  return true;
}

function hintMessage(
  step: string,
  companyId: string,
  status: CompanySetupStatus | undefined,
  statusLoading: boolean,
  isStepValidated: boolean,
): string | null {
  if (statusLoading) return 'Chargement…';
  if (step === 'intro' && companyId) return 'Filiale sélectionnée.';
  if (step === 'intro' && !companyId) return 'Sélectionnez une entreprise pour poursuivre.';
  if (!companyId) return 'Sélectionnez une filiale à l’étape précédente.';
  if (isCompanySetupStepBlocked(step, status)) return 'Import DSN requis avant cette étape.';
  if (step === 'dsn' && status && status.blocks.employees.total === 0 && !status.blocks.dsn.complete) {
    return 'Importez au moins un mois DSN pour continuer.';
  }
  if (isStepValidated) return 'Étape validée — vous pouvez revenir plus tard si besoin.';
  return null;
}

function nextLabel(wizardStep: string): string {
  if (wizardStep === 'intro') return 'Étape suivante';
  if (wizardStep === 'planning') return 'Voir le bilan';
  return 'Étape suivante';
}

export function CompanySetupWizardFooter({
  wizardStep,
  companyId,
  status,
  statusLoading,
  isStepValidated,
  showBack = true,
  onBack,
  onNext,
  onValidate,
  onUnvalidate,
  onClose,
}: Props) {
  const canContinue = canAdvance(wizardStep, companyId, status, statusLoading);
  const manualValidation = isSetupStepManuallyValidatable(wizardStep);
  const canMarkValidated = manualValidation && canValidate(wizardStep, companyId, status, statusLoading);
  const showSkipLink = canSkipIncomplete(wizardStep, companyId, status, statusLoading);
  const hint = hintMessage(wizardStep, companyId, status, statusLoading, isStepValidated);

  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-t bg-background px-4 py-2">
      <div className="flex shrink-0 items-center gap-2">
        {showBack ? (
          <Button type="button" variant="ghost" size="sm" className="h-8 px-2" onClick={onBack}>
            Retour
          </Button>
        ) : onClose ? (
          <Button type="button" variant="ghost" size="sm" className="h-8 px-2" onClick={onClose}>
            Fermer
          </Button>
        ) : (
          <span className="w-16" />
        )}
      </div>

      <div className="flex min-w-0 flex-1 items-center justify-end gap-2 sm:gap-3">
        {hint ? (
          <span className="hidden truncate text-xs text-muted-foreground lg:inline">{hint}</span>
        ) : null}

        {manualValidation && isStepValidated ? (
          <button
            type="button"
            className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline"
            onClick={onUnvalidate}
          >
            Retirer la validation
          </button>
        ) : null}

        {showSkipLink && !isStepValidated ? (
          <button
            type="button"
            className="shrink-0 text-xs text-muted-foreground underline-offset-2 hover:text-foreground hover:underline disabled:pointer-events-none disabled:opacity-40"
            onClick={onNext}
          >
            Passer cette étape
          </button>
        ) : null}

        {manualValidation && !isStepValidated ? (
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-8 shrink-0"
            disabled={!canMarkValidated}
            onClick={onValidate}
          >
            Valider l&apos;étape
          </Button>
        ) : manualValidation && isStepValidated ? (
          <span className="hidden shrink-0 items-center gap-1 text-xs font-medium text-emerald-700 sm:inline-flex">
            <Check className="h-3.5 w-3.5" aria-hidden />
            Validée
          </span>
        ) : null}

        <Button
          type="button"
          size="sm"
          className="h-8 shrink-0"
          disabled={!canContinue}
          onClick={onNext}
        >
          {nextLabel(wizardStep)}
        </Button>
      </div>
    </div>
  );
}
