import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info } from 'lucide-react';

export function WorkTimeHubIntro() {
  return (
    <Alert className="border-muted bg-muted/30">
      <Info className="h-4 w-4" />
      <AlertDescription className="text-sm leading-relaxed">
        <strong>Plafond annuel</strong> : combien d&apos;heures supplémentaires ont été
        consommées cette année, par rapport au seuil COR (220 h) et au plafond interne de
        pilotage.
        <br />
        <strong>Compte d&apos;heures</strong> : comment les HS sont gérées sur l&apos;année
        (annualisation 32/37 h, HS mises au compteur, récupérations) — indépendamment du
        plafond légal.
      </AlertDescription>
    </Alert>
  );
}
