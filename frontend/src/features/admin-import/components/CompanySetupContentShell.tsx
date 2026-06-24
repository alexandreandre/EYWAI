import type { ReactNode } from 'react';
import { Building2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';

export function CompanySetupPickCompanyHint() {
  return (
    <p className="text-sm text-muted-foreground rounded-lg border border-dashed px-4 py-3">
      Sélectionnez une entreprise dans le bandeau ci-dessus pour cette étape, ou choisissez-la
      directement dans le formulaire d’import.
    </p>
  );
}

export function CompanySetupEmptyState({
  onStartWizard,
}: {
  onStartWizard: () => void;
}) {
  return (
    <Card className="border-dashed">
      <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
        <div className="rounded-full bg-muted p-3">
          <Building2 className="h-6 w-6 text-muted-foreground" />
        </div>
        <div className="space-y-1 max-w-sm">
          <p className="font-medium">Choisissez une entreprise</p>
          <p className="text-sm text-muted-foreground">
            Sélectionnez une filiale dans le bandeau ci-dessus, ou lancez le parcours guidé pour
            configurer une nouvelle entreprise.
          </p>
        </div>
        <Button type="button" onClick={onStartWizard}>Lancer le parcours guidé</Button>
      </CardContent>
    </Card>
  );
}

export function CompanySetupContentShell({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border bg-card p-5 shadow-sm min-w-0">
      {children}
    </div>
  );
}
