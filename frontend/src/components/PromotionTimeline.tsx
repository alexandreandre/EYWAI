// frontend/src/components/PromotionTimeline.tsx
// Composant pour afficher une timeline visuelle du workflow de promotion

import React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { CheckCircle2, Circle, XCircle, Clock, FileText } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Promotion, PromotionStatus } from "@/api/promotions";

interface PromotionTimelineProps {
  promotion: Promotion;
  className?: string;
}

interface TimelineStep {
  key: PromotionStatus | "effective";
  label: string;
  description: string;
  icon: React.ReactNode;
  date?: string | null;
  actor?: string | null;
}

function formatDate(dateString: string | null | undefined): string {
  if (!dateString) return "";
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

export function PromotionTimeline({
  promotion,
  className,
}: PromotionTimelineProps) {
  const steps: TimelineStep[] = [
    {
      key: "draft",
      label: "Brouillon",
      description: "Promotion créée en brouillon",
      icon: <FileText className="h-5 w-5" />,
      date: promotion.created_at,
      actor: promotion.requested_by ? "Demandeur" : undefined,
    },
    {
      key: "pending_approval",
      label: "En attente d'approbation",
      description: "Soumission pour approbation",
      icon: <Clock className="h-5 w-5" />,
      date: promotion.status === "pending_approval" ? promotion.updated_at : null,
    },
    {
      key: "approved",
      label: "Approuvée",
      description: "Promotion approuvée",
      icon: <CheckCircle2 className="h-5 w-5" />,
      date: promotion.approved_at || null,
      actor: promotion.approved_by ? "Approbateur" : undefined,
    },
    {
      key: "effective",
      label: "Effective",
      description: "Changements appliqués",
      icon: <CheckCircle2 className="h-5 w-5" />,
      date:
        promotion.status === "effective"
          ? promotion.effective_date
          : null,
    },
  ];

  // Déterminer l'étape actuelle
  const getCurrentStepIndex = (): number => {
    switch (promotion.status) {
      case "draft":
        return 0;
      case "pending_approval":
        return 1;
      case "approved":
        return 2;
      case "effective":
        return 3;
      case "rejected":
        return -1; // Étape spéciale pour rejet
      case "cancelled":
        return -1; // Étape spéciale pour annulation
      default:
        return 0;
    }
  };

  const currentStepIndex = getCurrentStepIndex();
  const isRejected = promotion.status === "rejected";
  const isCancelled = promotion.status === "cancelled";

  return (
    <Card className={cn("w-full", className)}>
      <CardHeader>
        <CardTitle className="text-lg font-semibold">Progression</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {steps.map((step, index) => {
            const isCompleted = index < currentStepIndex;
            const isCurrent = index === currentStepIndex;
            const isFuture = index > currentStepIndex;

            // Ne pas afficher les étapes futures si la promotion est rejetée ou annulée
            if ((isRejected || isCancelled) && isFuture) {
              return null;
            }

            return (
              <div key={step.key} className="flex items-start gap-4">
                {/* Icône */}
                <div
                  className={cn(
                    "flex items-center justify-center rounded-full p-2 transition-colors",
                    isCompleted &&
                      "bg-green-100 text-green-600 dark:bg-green-900 dark:text-green-300",
                    isCurrent &&
                      "bg-blue-100 text-blue-600 dark:bg-blue-900 dark:text-blue-300",
                    isFuture &&
                      "bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-600"
                  )}
                >
                  {isCompleted ? (
                    <CheckCircle2 className="h-5 w-5" />
                  ) : isCurrent ? (
                    step.icon
                  ) : (
                    <Circle className="h-5 w-5" />
                  )}
                </div>

                {/* Contenu */}
                <div className="flex-1 space-y-1">
                  <div className="flex items-center justify-between">
                    <div>
                      <p
                        className={cn(
                          "font-medium",
                          isCompleted && "text-green-700 dark:text-green-300",
                          isCurrent && "text-blue-700 dark:text-blue-300",
                          isFuture && "text-gray-500 dark:text-gray-400"
                        )}
                      >
                        {step.label}
                      </p>
                      <p className="text-sm text-muted-foreground">
                        {step.description}
                      </p>
                    </div>
                    {step.date && (
                      <div className="text-right">
                        <p className="text-xs text-muted-foreground">
                          {formatDate(step.date)}
                        </p>
                        {step.actor && (
                          <p className="text-xs text-muted-foreground">
                            {step.actor}
                          </p>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })}

          {/* Étape de rejet */}
          {isRejected && (
            <div className="flex items-start gap-4 pt-2 border-t">
              <div className="flex items-center justify-center rounded-full p-2 bg-red-100 text-red-600 dark:bg-red-900 dark:text-red-300">
                <XCircle className="h-5 w-5" />
              </div>
              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-red-700 dark:text-red-300">
                      Rejetée
                    </p>
                    {promotion.rejection_reason && (
                      <p className="text-sm text-muted-foreground">
                        {promotion.rejection_reason}
                      </p>
                    )}
                  </div>
                  {promotion.updated_at && (
                    <p className="text-xs text-muted-foreground">
                      {formatDate(promotion.updated_at)}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Étape d'annulation */}
          {isCancelled && (
            <div className="flex items-start gap-4 pt-2 border-t">
              <div className="flex items-center justify-center rounded-full p-2 bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400">
                <XCircle className="h-5 w-5" />
              </div>
              <div className="flex-1 space-y-1">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-medium text-gray-700 dark:text-gray-300">
                      Annulée
                    </p>
                    <p className="text-sm text-muted-foreground">
                      Promotion annulée
                    </p>
                  </div>
                  {promotion.updated_at && (
                    <p className="text-xs text-muted-foreground">
                      {formatDate(promotion.updated_at)}
                    </p>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
