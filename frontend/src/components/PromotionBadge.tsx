// frontend/src/components/PromotionBadge.tsx
// Badge pour afficher le statut ou le type d'une promotion

import React from "react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import type { PromotionStatus, PromotionType } from "@/api/promotions";

const STATUS_LABELS: Record<PromotionStatus, string> = {
  draft: "Brouillon",
  pending_approval: "En attente d'approbation",
  approved: "Approuvée",
  rejected: "Rejetée",
  effective: "Effective",
  cancelled: "Annulée",
};

const STATUS_CLASSES: Record<PromotionStatus, string> = {
  draft: "bg-gray-100 text-gray-700 border-gray-200",
  pending_approval: "bg-amber-100 text-amber-700 border-amber-200",
  approved: "bg-green-100 text-green-700 border-green-200",
  rejected: "bg-red-100 text-red-700 border-red-200",
  effective: "bg-emerald-100 text-emerald-700 border-emerald-200",
  cancelled: "bg-slate-100 text-slate-600 border-slate-200",
};

const TYPE_LABELS: Record<PromotionType, string> = {
  poste: "Changement de poste",
  salaire: "Augmentation de salaire",
  statut: "Changement de statut",
  classification: "Changement de classification",
  mixte: "Promotion mixte",
};

const TYPE_CLASSES: Record<PromotionType, string> = {
  poste: "bg-blue-100 text-blue-700 border-blue-200",
  salaire: "bg-purple-100 text-purple-700 border-purple-200",
  statut: "bg-indigo-100 text-indigo-700 border-indigo-200",
  classification: "bg-cyan-100 text-cyan-700 border-cyan-200",
  mixte: "bg-gradient-to-r from-blue-100 to-purple-100 text-gray-700 border-gray-200",
};

const STATUS_TOOLTIPS: Record<PromotionStatus, string> = {
  draft: "Promotion en cours de création, non soumise pour approbation",
  pending_approval: "Promotion soumise et en attente de validation par un administrateur",
  approved: "Promotion approuvée, en attente de la date d'effet pour être appliquée",
  rejected: "Promotion rejetée, les changements ne seront pas appliqués",
  effective: "Promotion effective, les changements ont été appliqués à l'employé",
  cancelled: "Promotion annulée avant d'être effective",
};

const TYPE_TOOLTIPS: Record<PromotionType, string> = {
  poste: "Changement du titre de poste de l'employé",
  salaire: "Augmentation ou modification du salaire de base",
  statut: "Changement du statut (Cadre / Non-Cadre)",
  classification: "Modification de la classification (coefficient, classe d'emploi)",
  mixte: "Promotion combinant plusieurs types de changements simultanés",
};

interface PromotionBadgeProps {
  status?: PromotionStatus | null;
  type?: PromotionType | null;
  variant?: "status" | "type";
  compact?: boolean;
  className?: string;
  showTooltip?: boolean; // Option pour afficher/masquer le tooltip
}

export function PromotionBadge({
  status,
  type,
  variant = "status",
  compact = false,
  className,
  showTooltip = true,
}: PromotionBadgeProps) {
  // Si variant = "status", afficher le statut
  if (variant === "status") {
    if (!status) return null;

    const label = STATUS_LABELS[status] ?? status;
    const statusClass = STATUS_CLASSES[status] ?? "bg-gray-100 text-gray-700 border-gray-200";
    const tooltip = STATUS_TOOLTIPS[status];

    const badge = (
      <Badge
        variant="outline"
        className={cn(
          statusClass,
          compact ? "text-xs" : "font-semibold text-sm px-3 py-1",
          showTooltip && "cursor-help",
          className
        )}
        aria-label={`Statut: ${label}. ${tooltip}`}
      >
        {label}
      </Badge>
    );

    if (showTooltip && tooltip) {
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>{badge}</TooltipTrigger>
            <TooltipContent>
              <p className="max-w-xs">{tooltip}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    }

    return badge;
  }

  // Si variant = "type", afficher le type
  if (variant === "type") {
    if (!type) return null;

    const label = TYPE_LABELS[type] ?? type;
    const typeClass = TYPE_CLASSES[type] ?? "bg-gray-100 text-gray-700 border-gray-200";
    const tooltip = TYPE_TOOLTIPS[type];

    const badge = (
      <Badge
        variant="outline"
        className={cn(
          typeClass,
          compact ? "text-xs" : "font-semibold text-sm px-3 py-1",
          showTooltip && "cursor-help",
          className
        )}
        aria-label={`Type: ${label}. ${tooltip}`}
      >
        {label}
      </Badge>
    );

    if (showTooltip && tooltip) {
      return (
        <TooltipProvider>
          <Tooltip>
            <TooltipTrigger asChild>{badge}</TooltipTrigger>
            <TooltipContent>
              <p className="max-w-xs">{tooltip}</p>
            </TooltipContent>
          </Tooltip>
        </TooltipProvider>
      );
    }

    return badge;
  }

  return null;
}
