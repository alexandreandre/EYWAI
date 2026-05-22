// frontend/src/components/AnnualReviewBadge.tsx
// Badge de statut pour les entretiens

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
  planifie: "border-transparent bg-primary/10 text-primary",
  en_attente_acceptation: "border-transparent bg-warning/15 text-warning",
  accepte: "border-transparent bg-success/15 text-success",
  refuse: "border-transparent bg-destructive/15 text-destructive",
  realise: "border-transparent bg-success/15 text-success",
  cloture: "border-transparent bg-muted text-muted-foreground",
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
  const statusClass = STATUS_CLASSES[status] ?? "bg-muted text-muted-foreground";

  return (
    <Badge
      variant="outline"
      className={cn(
        statusClass,
        compact ? "text-xs font-normal" : "font-semibold text-sm px-3 py-1",
        className
      )}
    >
      {label}
    </Badge>
  );
}
