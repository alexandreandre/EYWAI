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
};

function sheetTitle(config: DsnImportLaunchConfig | null): string {
  if (!config) return 'Import DSN';
  if (config.mode === 'onboarding') return 'Nouveau dossier (onboarding)';
  if (config.suggestedPeriod) return `Import DSN — ${config.suggestedPeriod}`;
  return 'Import DSN mensuel';
}

export function DsnImportSheet({
  open,
  onOpenChange,
  launchConfig,
  initialFiles,
}: Props) {
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="flex w-full flex-col overflow-y-auto sm:max-w-[640px]">
        <SheetHeader className="shrink-0 text-left">
          <SheetTitle>{sheetTitle(launchConfig)}</SheetTitle>
          <SheetDescription>
            {launchConfig?.mode === 'onboarding'
              ? 'Constituez le dossier paie initial (plusieurs mois possibles).'
              : 'Analysez et validez la DSN mensuelle sans quitter la vue d\u2019ensemble.'}
          </SheetDescription>
        </SheetHeader>
        {launchConfig && (
          <div className="mt-4 flex-1 pb-6">
            <DsnImportWizard
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
