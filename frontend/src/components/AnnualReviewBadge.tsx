// frontend/src/components/AnnualReviewBadge.tsx
// Badge de statut pour les entretiens

import React from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { AnnualReviewStatus } from "@/api/annualReviews";

const STATUS_LABELS: Record<AnnualReviewStatus, string> = {
  planifie: "Planifié",
  en_attente_acceptation: "En attente d'acceptation",
  accepte: "Accepté",
  refuse: "Refusé",
  realise: "Réalisé",
  cloture: "Clôturé",
};

const STATUS_CLASSES: Record<AnnualReviewStatus, string> = {
  planifie: "bg-blue-100 text-blue-700 border-blue-200",
  en_attente_acceptation: "bg-amber-100 text-amber-700 border-amber-200",
  accepte: "bg-green-100 text-green-700 border-green-200",
  refuse: "bg-red-100 text-red-700 border-red-200",
  realise: "bg-emerald-100 text-emerald-700 border-emerald-200",
  cloture: "bg-slate-100 text-slate-600 border-slate-200",
};

interface AnnualReviewBadgeProps {
  status: AnnualReviewStatus | null | undefined;
  compact?: boolean;
  className?: string;
}

export function AnnualReviewBadge({
  status,
  compact = false,
  className,
}: AnnualReviewBadgeProps) {
  if (!status) return null;

  const label = STATUS_LABELS[status] ?? status;
  const statusClass = STATUS_CLASSES[status] ?? "bg-gray-100 text-gray-700 border-gray-200";

  if (compact) {
    return (
      <Badge
        variant="outline"
        className={cn(statusClass, "text-xs", className)}
      >
        {label}
      </Badge>
    );
  }

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <Badge
        variant="outline"
        className={cn(statusClass, "font-semibold text-sm px-3 py-1")}
      >

        {label}
      </Badge>
    </div>
  );
}
