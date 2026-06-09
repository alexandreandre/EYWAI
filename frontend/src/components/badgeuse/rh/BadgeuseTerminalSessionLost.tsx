import { AlertTriangle } from 'lucide-react';
import { Card } from '@/components/ui/card';

export function BadgeuseTerminalSessionLost() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <Card className="max-w-md space-y-4 p-8 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-amber-100 text-amber-700">
          <AlertTriangle className="h-6 w-6" aria-hidden />
        </div>
        <div className="space-y-2">
          <h1 className="text-xl font-semibold">Badgeuse indisponible</h1>
          <p className="text-sm text-muted-foreground">
            Cet appareil n&apos;est pas encore activé pour la badgeuse, ou l&apos;accès
            a été révoqué. Depuis un compte RH, ouvrez Badgeuse et cliquez sur
            « Ouvrir la badgeuse sur cet appareil ».
          </p>
          <p className="text-sm font-medium">
            Contactez le service RH pour reconfigurer le terminal badgeuse.
          </p>
        </div>
      </Card>
    </div>
  );
}
