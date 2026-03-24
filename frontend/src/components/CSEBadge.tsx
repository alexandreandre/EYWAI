// frontend/src/components/CSEBadge.tsx
// Badge pour afficher le statut élu CSE d'un employé

import React from "react";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Users, Calendar, Clock } from "lucide-react";
import type { ElectedMemberRole } from "@/api/cse";

interface CSEBadgeProps {
  role: ElectedMemberRole;
  college?: string | null;
  startDate: string;
  endDate: string;
  daysRemaining?: number | null;
  compact?: boolean;
}

const ROLE_LABELS: Record<ElectedMemberRole, string> = {
  titulaire: "Titulaire",
  suppleant: "Suppléant",
  secretaire: "Secrétaire",
  tresorier: "Trésorier",
  autre: "Autre",
};

const ROLE_CLASSES: Record<ElectedMemberRole, string> = {
  titulaire: "bg-blue-100 text-blue-800 border-blue-200",
  suppleant: "bg-green-100 text-green-800 border-green-200",
  secretaire: "bg-purple-100 text-purple-800 border-purple-200",
  tresorier: "bg-orange-100 text-orange-800 border-orange-200",
  autre: "bg-gray-100 text-gray-800 border-gray-200",
};

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

export function CSEBadge({
  role,
  college,
  startDate,
  endDate,
  daysRemaining,
  compact = false,
}: CSEBadgeProps) {
  const isExpiringSoon = daysRemaining !== null && daysRemaining <= 90;
  const isExpired = daysRemaining !== null && daysRemaining < 0;

  const badgeContent = (
    <Badge className={ROLE_CLASSES[role] || ROLE_CLASSES.autre}>
      <Users className="h-3 w-3 mr-1" />
      {compact ? ROLE_LABELS[role] : `Élu CSE - ${ROLE_LABELS[role]}`}
      {college && !compact && ` (${college})`}
    </Badge>
  );

  if (compact) {
    return badgeContent;
  }

  const tooltipContent = (
    <div className="space-y-1 text-sm">
      <div className="font-semibold">Mandat CSE</div>
      <div>Rôle: {ROLE_LABELS[role]}</div>
      {college && <div>Collège: {college}</div>}
      <div className="flex items-center gap-1">
        <Calendar className="h-3 w-3" />
        <span>Début: {formatDate(startDate)}</span>
      </div>
      <div className="flex items-center gap-1">
        <Calendar className="h-3 w-3" />
        <span>Fin: {formatDate(endDate)}</span>
      </div>
      {daysRemaining !== null && (
        <div className={`flex items-center gap-1 ${isExpired ? "text-red-400" : isExpiringSoon ? "text-orange-400" : ""}`}>
          <Clock className="h-3 w-3" />
          <span>
            {isExpired
              ? `Expiré depuis ${Math.abs(daysRemaining)} jour${Math.abs(daysRemaining) > 1 ? "s" : ""}`
              : `${daysRemaining} jour${daysRemaining > 1 ? "s" : ""} restant${daysRemaining > 1 ? "s" : ""}`}
          </span>
        </div>
      )}
    </div>
  );

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger asChild>{badgeContent}</TooltipTrigger>
        <TooltipContent side="bottom" className="max-w-xs">
          {tooltipContent}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
