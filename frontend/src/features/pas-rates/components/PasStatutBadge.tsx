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
import { AIDE_STATUT_PAS } from "@/features/pas-rates/lib/statutsPas";

type Variant = "success" | "warning" | "danger" | "secondary";

const PRESENTATION: Record<PasStatut, { variant: Variant; aide: string }> = {
  a_jour: { variant: "success", aide: AIDE_STATUT_PAS.a_jour },
  bareme: { variant: "secondary", aide: AIDE_STATUT_PAS.bareme },
  a_rafraichir: { variant: "warning", aide: AIDE_STATUT_PAS.a_rafraichir },
  manquant: { variant: "secondary", aide: AIDE_STATUT_PAS.manquant },
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
