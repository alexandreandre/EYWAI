import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info } from 'lucide-react';

export function WorkTimeHubIntro() {
  return (
    <Alert className="border-muted bg-muted/30">
      <Info className="h-4 w-4" />
      <AlertDescription className="text-sm leading-relaxed">
        <strong>Plafond annuel</strong> : les heures supplémentaires faites cette année,
        face au contingent (220 h par défaut) et au repos compensateur qu&apos;il déclenche.
        <br />
        <strong>Compteur récup</strong> : les heures sup mises au compteur au lieu d&apos;être
        payées, les récupérations prises, et ce qui reste à prendre ou à payer.
      </AlertDescription>
    </Alert>
  );
}
