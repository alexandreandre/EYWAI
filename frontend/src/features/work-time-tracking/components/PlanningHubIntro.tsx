import { Alert, AlertDescription } from '@/components/ui/alert';
import { Info } from 'lucide-react';

export function PlanningHubIntro() {
  return (
    <Alert className="border-muted bg-muted/30">
      <Info className="h-4 w-4" />
      <AlertDescription className="text-sm leading-relaxed">
        <strong>Modèles de semaine</strong> : heures contractuelles nettes et détail des pauses
        (payées incluses / repas déduit).
        <br />
        <strong>Créneaux pointage</strong> : déduction repas au badgeage et grilles horaires
        théoriques.
        <br />
        <strong>Types de poste planning</strong> : postes équipes (3×8…) — les pauses payées
        peuvent rester incluses dans le salaire de base sans ligne bulletin séparée.
      </AlertDescription>
    </Alert>
  );
}
