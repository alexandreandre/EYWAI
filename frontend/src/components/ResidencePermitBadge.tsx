// frontend/src/components/ResidencePermitBadge.tsx
/**
 * Composant pour afficher le badge de statut du titre de séjour.
 * 
 * Ce composant est uniquement responsable de la présentation.
 * Il ne recalcule jamais le statut, qui doit être fourni par le backend.
 * 
 * Conforme à la spécification UX définie dans SPECIFICATION_UX_TITRES_SEJOUR_FICHE_EMPLOYE.md
 */

import React from "react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export interface ResidencePermitData {
  is_subject_to_residence_permit: boolean;
  residence_permit_status?: "valid" | "to_renew" | "expired" | "to_complete" | null;
  residence_permit_expiry_date?: string | null; // Format ISO (YYYY-MM-DD)
  residence_permit_days_remaining?: number | null;
  residence_permit_data_complete?: boolean | null;
}

interface ResidencePermitBadgeProps {
  data: ResidencePermitData | null | undefined;
  className?: string;
}

/**
 * Génère le message du tooltip selon le statut et les données disponibles.
 */
function getTooltipMessage(
  status: string | null | undefined,
  expiryDate: string | null | undefined
): string | null {
  if (!status) return null;

  // Formater la date si disponible
  let formattedDate = null;
  if (expiryDate) {
    try {
      const date = new Date(expiryDate);
      formattedDate = date.toLocaleDateString("fr-FR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
      });
    } catch (e) {
      // Si la date est invalide, on l'ignore
    }
  }

  switch (status) {
    case "valid":
      return formattedDate ? `Expire le ${formattedDate}` : null;

    case "to_renew":
      return formattedDate
        ? `Expire le ${formattedDate} — renouvellement à anticiper`
        : null;

    case "expired":
      return formattedDate
        ? `Expiré depuis le ${formattedDate} — action immédiate requise`
        : null;

    case "to_complete":
      return "Date d'expiration non renseignée";

    default:
      return null;
  }
}

/**
 * Obtient les classes CSS et le libellé selon le statut.
 */
function getStatusConfig(status: string | null | undefined): {
  label: string;
  className: string;
} {
  switch (status) {
    case "valid":
      return {
        label: "Valide",
        className: "bg-green-100 text-green-700 border-green-200",
      };

    case "to_renew":
      return {
        label: "À renouveler",
        className: "bg-orange-100 text-orange-700 border-orange-200",
      };

    case "expired":
      return {
        label: "Expiré",
        className: "bg-red-100 text-red-700 border-red-200",
      };

    case "to_complete":
      return {
        label: "À renseigner",
        className: "bg-gray-100 text-gray-700 border-gray-200",
      };

    default:
      // Fallback sûr en cas de statut inconnu
      return {
        label: "À renseigner",
        className: "bg-gray-100 text-gray-700 border-gray-200",
      };
  }
}

export function ResidencePermitBadge({
  data,
  className,
}: ResidencePermitBadgeProps) {
  // CAS 1: Données non disponibles ou employé non soumis
  if (
    !data ||
    !data.is_subject_to_residence_permit ||
    !data.residence_permit_status
  ) {
    // Aucun affichage selon la spécification UX
    return null;
  }

  const status = data.residence_permit_status;
  const expiryDate = data.residence_permit_expiry_date;
  const { label, className: statusClassName } = getStatusConfig(status);
  const tooltipMessage = getTooltipMessage(status, expiryDate);

  // Si un tooltip est disponible, l'afficher
  if (tooltipMessage) {
    return (
      <TooltipProvider>
        <Tooltip>
          <TooltipTrigger asChild>
            <div className={cn("flex items-center gap-2", className)}>
              <span className="text-sm text-muted-foreground">
                Titre de séjour:
              </span>
              <Badge
                variant="outline"
                className={cn(statusClassName, "cursor-help")}
              >
                {label}
              </Badge>
            </div>
          </TooltipTrigger>
          <TooltipContent>
            <p>{tooltipMessage}</p>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  // Sinon, afficher sans tooltip
  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-sm text-muted-foreground">Titre de séjour:</span>
      <Badge variant="outline" className={statusClassName}>
        {label}
      </Badge>
    </div>
  );
}

