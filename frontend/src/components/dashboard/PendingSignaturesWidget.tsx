import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
  CheckCircle,
  Mail,
  RefreshCw,
  X,
} from "lucide-react";

import {
  getPendingSignaturesME,
  getPendingSignaturesRH,
  sendSignatureReminder,
  type PendingSignatureItem,
} from "@/api/signatures";
import { useCompanyOptional } from "@/contexts/CompanyContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/use-toast";
import { getUserErrorMessage } from "@/lib/errorMessages";
import { cn } from "@/lib/utils";

const DOC_MAX = 40;

function truncateDocument(name: string): string {
  const t = name.trim();
  if (t.length <= DOC_MAX) return t;
  return `${t.slice(0, DOC_MAX)}…`;
}

function parseDateMs(iso?: string | null): number | null {
  if (!iso) return null;
  const d = Date.parse(iso);
  return Number.isNaN(d) ? null : d;
}

function daysSinceSent(sentAt?: string): number | null {
  const ms = parseDateMs(sentAt);
  if (ms === null) return null;
  const diff = Date.now() - ms;
  return Math.max(0, Math.floor(diff / (1000 * 60 * 60 * 24)));
}

function formatRhSignerLine(item: PendingSignatureItem): string {
  const fn = (item.employee_first_name || "").trim();
  const ln = (item.employee_last_name || "").trim();
  if (fn || ln) {
    const last = ln.toUpperCase();
    return `${fn} ${last}`.trim();
  }
  return "Signataire inconnu";
}

function formatDelayText(
  item: PendingSignatureItem,
  mode: "rh" | "employee"
): string {
  const d = item.days_until_expiry;
  if (mode === "employee" && d != null && d < 3) {
    return `Expire dans ${d}j`;
  }
  if (mode === "rh" && item.is_urgent && d != null) {
    return `Expire dans ${d}j`;
  }
  const x = daysSinceSent(item.sent_at);
  if (x !== null) {
    return `En attente · J+${x}`;
  }
  return "En attente";
}

function rhRowClass(item: PendingSignatureItem): string {
  if (item.is_urgent) {
    return "rounded-lg border border-orange-200 bg-orange-50 p-3 dark:border-orange-900/50 dark:bg-orange-950/30";
  }
  return "rounded-lg border border-blue-100 bg-blue-50 p-3 dark:border-blue-900/40 dark:bg-blue-950/25";
}

function employeeRowClass(item: PendingSignatureItem): string {
  const d = item.days_until_expiry;
  if (d != null && d < 3) {
    return "rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900/50 dark:bg-red-950/30";
  }
  if (d != null && d >= 3 && d <= 7) {
    return "rounded-lg border border-orange-200 bg-orange-50 p-3 dark:border-orange-900/50 dark:bg-orange-950/30";
  }
  return "rounded-lg border border-blue-100 bg-blue-50 p-3 dark:border-blue-900/40 dark:bg-blue-950/25";
}

export interface PendingSignaturesWidgetProps {
  mode: "rh" | "employee";
}

export function PendingSignaturesWidget({ mode }: PendingSignaturesWidgetProps) {
  const [isVisible, setIsVisible] = useState(true);
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const companyCtx = useCompanyOptional();

  const apiCall = mode === "rh" ? getPendingSignaturesRH : getPendingSignaturesME;

  const {
    data,
    isPending,
    isLoading,
    isFetching,
    isError,
    error,
    refetch,
    isRefetching,
  } = useQuery({
    queryKey: ["pending-signatures", mode],
    queryFn: apiCall,
    staleTime: 0,
  });

  const remindMutation = useMutation({
    mutationFn: sendSignatureReminder,
    onSuccess: (result) => {
      if (result.success) {
        toast({
          title: "Relance envoyée",
          description: "Le signataire a été relancé.",
        });
        void queryClient.invalidateQueries({ queryKey: ["pending-signatures"] });
      } else {
        toast({
          title: "Relance impossible",
          description: result.error || "Une erreur est survenue.",
          variant: "destructive",
        });
      }
    },
    onError: (e: unknown) => {
      toast({
        title: "Relance impossible",
        description: getUserErrorMessage(e, "La relance n’a pas pu être envoyée. Réessayez."),
        variant: "destructive",
      });
    },
  });

  const companyLabel =
    companyCtx?.activeCompany?.company_name?.trim() || "Votre entreprise";

  /** Chargement initial ou première réponse pas encore disponible : en-tête + skeleton. */
  const showLoadingSkeleton =
    !isError &&
    (isPending || isLoading || (isFetching && data === undefined));

  const title =
    mode === "rh" ? "Signatures en attente" : "Mes signatures en attente";

  const total = data?.total ?? 0;

  if (!isVisible) {
    if (mode === "employee" && !showLoadingSkeleton && !isError && total > 0) {
      return (
        <div
          className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 dark:border-blue-900/50 dark:bg-blue-950/30"
          role="status"
        >
          <p className="text-sm font-medium text-blue-900 dark:text-blue-100">
            {total} signature{total > 1 ? "s" : ""} en attente
          </p>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={() => setIsVisible(true)}
          >
            Rouvrir
          </Button>
        </div>
      );
    }
    return null;
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row flex-wrap items-center gap-2 space-y-0 pb-2">
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <Mail className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden />
          <CardTitle className={cn("font-semibold", mode === "employee" ? "text-lg" : "text-base")}>
            {title}
          </CardTitle>
          <Badge
            variant="secondary"
            className={cn(
              "shrink-0",
              total > 0
                ? "border-blue-200 bg-blue-100 text-blue-900 dark:border-blue-800 dark:bg-blue-950 dark:text-blue-100"
                : "bg-muted text-muted-foreground"
            )}
          >
            {total}
          </Badge>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => void refetch()}
            aria-label="Rafraîchir"
          >
            <RefreshCw
              className={cn("h-4 w-4", isRefetching && "animate-spin")}
              aria-hidden
            />
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={() => setIsVisible(false)}
            aria-label="Fermer le widget"
          >
            <X className="h-4 w-4" aria-hidden />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 pt-0">
        {showLoadingSkeleton && (
          <div className="space-y-2" aria-busy="true">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {isError && (
          <div className="rounded-md border border-destructive/30 bg-destructive/5 p-4 text-sm">
            <p className="font-medium text-destructive">Données non disponibles.</p>
            <p className="mt-1 text-muted-foreground">
              {error instanceof Error ? error.message : "Erreur inconnue."}
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={() => void refetch()}
            >
              Réessayer
            </Button>
          </div>
        )}

        {!showLoadingSkeleton && !isError && data && (
          <>
            {total === 0 && (
              <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed bg-muted/30 py-8 text-center">
                <CheckCircle className="h-10 w-10 text-emerald-600" aria-hidden />
                <p className="text-sm font-medium text-foreground">
                  Aucune signature en attente
                </p>
              </div>
            )}

            {total > 0 && (
              <ul className="space-y-2">
                {data.items.map((item) => (
                  <li
                    key={item.id}
                    className={mode === "rh" ? rhRowClass(item) : employeeRowClass(item)}
                  >
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0 flex-1 space-y-1">
                        <p className="truncate text-sm font-semibold text-foreground">
                          {truncateDocument(item.document_name)}
                        </p>
                        {mode === "rh" ? (
                          <p className="text-xs text-muted-foreground">
                            Signataire : {formatRhSignerLine(item)}
                          </p>
                        ) : (
                          <p className="text-xs text-muted-foreground">
                            Expéditeur : {companyLabel}
                          </p>
                        )}
                        <p
                          className={cn(
                            "text-xs font-medium",
                            mode === "employee" &&
                              item.days_until_expiry != null &&
                              item.days_until_expiry < 3
                              ? "text-red-700 dark:text-red-300"
                              : item.is_urgent
                                ? "text-orange-700 dark:text-orange-300"
                                : "text-muted-foreground"
                          )}
                        >
                          {formatDelayText(item, mode)}
                        </p>
                      </div>
                      <div className="flex shrink-0 flex-col gap-2 sm:items-end">
                        {mode === "rh" ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={remindMutation.isPending}
                            onClick={() => remindMutation.mutate(item.id)}
                          >
                            Relancer
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={!item.yousign_procedure_id}
                            onClick={() => {
                              if (!item.yousign_procedure_id) return;
                              window.open(
                                `https://app.yousign.com/procedure/${item.yousign_procedure_id}`,
                                "_blank",
                                "noopener,noreferrer"
                              );
                            }}
                          >
                            Signer maintenant →
                          </Button>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}

            <div className="border-t pt-3">
              {mode === "rh" ? (
                <button
                  type="button"
                  className="text-sm font-medium text-primary hover:underline"
                  onClick={() =>
                    navigate("/annual-reviews?signature_status=pending")
                  }
                >
                  Voir toutes les procédures ({total}) →
                </button>
              ) : (
                <Link
                  to="/employee/documents"
                  className="text-sm font-medium text-primary hover:underline"
                >
                  Voir mes documents →
                </Link>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
