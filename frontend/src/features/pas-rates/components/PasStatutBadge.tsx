// Badge de statut d'un taux de prélèvement à la source.
// Ne recalcule jamais le statut : il vient du backend, qui seul connaît la
// période d'origine du taux.

import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import type { PasStatut } from "@/api/pasRates";

type Variant = "success" | "warning" | "danger" | "secondary";

const PRESENTATION: Record<PasStatut, { variant: Variant; aide: string }> = {
  a_jour: {
    variant: "success",
    aide: "Taux transmis par la DGFiP, reçu récemment.",
  },
  bareme: {
    variant: "secondary",
    aide:
      "La DGFiP n'a pas encore transmis de taux personnalisé : c'est le barème par défaut qui s'applique. Il ne se périme pas — le moteur le recalcule à chaque paie sur la rémunération du mois, et le taux affiché ici est celui de la dernière DSN.",
  },
  a_rafraichir: {
    variant: "warning",
    aide:
      "Ce taux date de plus de deux mois, ou sa période d'origine est inconnue. Déposez la dernière DSN ou le dernier compte rendu métier pour le rafraîchir.",
  },
  manquant: {
    variant: "danger",
    aide:
      "Aucun taux connu : le bulletin prélève 0 % sans que personne l'ait décidé.",
  },
};

interface PasStatutBadgeProps {
  statut: PasStatut;
  libelle: string;
  className?: string;
}

export function PasStatutBadge({ statut, libelle, className }: PasStatutBadgeProps) {
  const presentation = PRESENTATION[statut];
  if (!presentation) {
    return <Badge variant="secondary" className={className}>{libelle}</Badge>;
  }
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>
          <Badge variant={presentation.variant} className={className}>
            {libelle}
          </Badge>
        </TooltipTrigger>
        <TooltipContent className="max-w-xs">{presentation.aide}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
