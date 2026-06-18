import type { DsnImportLaunchConfig } from '@/api/dsnImport';
import { DsnImportWizard } from './DsnImportWizard';
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet';

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  launchConfig: DsnImportLaunchConfig | null;
  initialFiles?: File[];
  sessionKey?: string | null;
};

function sheetTitle(config: DsnImportLaunchConfig | null): string {
  if (!config) return 'Import DSN';
  if (config.mode === 'onboarding') return 'Nouveau dossier (onboarding)';
  if (config.reimport && config.suggestedPeriod) {
    return `Réimporter — ${config.suggestedPeriod}`;
  }
  if (config.suggestedPeriod) return `Import DSN — ${config.suggestedPeriod}`;
  return 'Import DSN mensuel';
}

function sheetDescription(config: DsnImportLaunchConfig | null): string {
  if (!config) return '';
  if (config.mode === 'onboarding') {
    return 'Constituez le dossier paie initial (plusieurs mois possibles).';
  }
  if (config.reimport) {
    return 'Remplace les cumuls du mois et relance la réconciliation effectifs. Les fiches salariés ne sont pas supprimées.';
  }
  return 'Analysez et validez la DSN mensuelle sans quitter la vue d\u2019ensemble.';
}

export function DsnImportSheet({
  open,
  onOpenChange,
  launchConfig,
  initialFiles,
  sessionKey,
}: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col overflow-y-auto sm:max-w-[640px]">
        <SheetHeader className="shrink-0 text-left">
          <SheetTitle>{sheetTitle(launchConfig)}</SheetTitle>
          <SheetDescription>{sheetDescription(launchConfig)}</SheetDescription>
        </SheetHeader>
        {launchConfig && sessionKey && (
          <div className="mt-4 flex-1 pb-6">
            <DsnImportWizard
              key={sessionKey}
              launchConfig={launchConfig}
              initialFiles={initialFiles}
              embedded
              onResetLaunch={() => onOpenChange(false)}
            />
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
