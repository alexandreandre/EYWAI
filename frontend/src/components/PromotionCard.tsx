// frontend/src/components/PromotionCard.tsx
// Composant pour afficher une carte résumée d'une promotion

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { PromotionBadge } from "./PromotionBadge";
import { ArrowRight, Calendar, User, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import type { PromotionListItem, Promotion } from "@/api/promotions";

interface PromotionCardProps {
  promotion: PromotionListItem | Promotion;
  onClick?: () => void;
  className?: string;
}

function formatDate(dateString: string): string {
  try {
    return new Date(dateString).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    });
  } catch {
    return dateString;
  }
}

function formatCurrency(salary: { valeur: number; devise: string } | null): string {
  if (!salary || !salary.valeur) return "—";
  return `${salary.valeur.toLocaleString("fr-FR")} ${salary.devise || "EUR"}`;
}

function getPromotionSummary(promotion: PromotionListItem | Promotion): string {
  const changes: string[] = [];

  if (promotion.new_job_title) {
    changes.push("Poste");
  }
  if (promotion.new_salary) {
    changes.push("Salaire");
  }
  if (promotion.new_statut) {
    changes.push("Statut");
  }
  if ("new_classification" in promotion && promotion.new_classification) {
    changes.push("Classification");
  }
  if (promotion.grant_rh_access) {
    changes.push("Accès RH");
  }

  if (changes.length === 0) {
    return "Promotion";
  }

  return changes.join(" • ");
}

export function PromotionCard({
  promotion,
  onClick,
  className,
}: PromotionCardProps) {
  const employeeName =
    "first_name" in promotion && "last_name" in promotion
      ? `${promotion.first_name} ${promotion.last_name}`
      : "Employé";

  const summary = getPromotionSummary(promotion);

  return (
    <Card
      className={cn(
        "w-full transition-all duration-200 hover:shadow-md",
        onClick && "cursor-pointer hover:border-primary",
        className
      )}
      onClick={onClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-base font-semibold mb-2">
              {employeeName}
            </CardTitle>
            <div className="flex items-center gap-2 mb-2">
              <PromotionBadge status={promotion.status} compact />
              <PromotionBadge type={promotion.promotion_type} variant="type" compact />
            </div>
          </div>
          {onClick && (
            <ArrowRight className="h-5 w-5 text-muted-foreground flex-shrink-0" />
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {/* Résumé des changements */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <TrendingUp className="h-4 w-4" />
          <span>{summary}</span>
        </div>

        {/* Détails spécifiques */}
        <div className="space-y-2 text-sm">
          {promotion.new_job_title && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Poste:</span>
              <span className="font-medium">{promotion.new_job_title}</span>
            </div>
          )}

          {promotion.new_salary && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Salaire:</span>
              <span className="font-medium">
                {formatCurrency(promotion.new_salary)}
              </span>
            </div>
          )}

          {promotion.new_statut && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Statut:</span>
              <span className="font-medium">{promotion.new_statut}</span>
            </div>
          )}

          {promotion.grant_rh_access && promotion.new_rh_access && (
            <div className="flex items-center gap-2">
              <span className="text-muted-foreground">Accès RH:</span>
              <span className="font-medium">
                {promotion.new_rh_access === "collaborateur_rh"
                  ? "Collaborateur RH"
                  : promotion.new_rh_access === "rh"
                  ? "RH"
                  : "Administrateur"}
              </span>
            </div>
          )}
        </div>

        {/* Date d'effet */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground pt-2 border-t">
          <Calendar className="h-4 w-4" />
          <span>
            Date d'effet: <strong>{formatDate(promotion.effective_date)}</strong>
          </span>
        </div>

        {/* Demandeur/Approbateur */}
        {"requested_by_name" in promotion && promotion.requested_by_name && (
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <User className="h-3 w-3" />
            <span>
              Demandé par: {promotion.requested_by_name}
              {promotion.approved_by_name && ` • Approuvé par: ${promotion.approved_by_name}`}
            </span>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
