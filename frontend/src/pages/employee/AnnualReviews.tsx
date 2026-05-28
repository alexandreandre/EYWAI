// frontend/src/pages/employee/AnnualReviews.tsx
// Page employé : Liste de tous les entretiens

import { useMemo, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import { getMyAnnualReviews, INTERVIEW_TYPE_LABELS } from "@/api/annualReviews";
import type { AnnualReview, InterviewType } from "@/api/annualReviews";
import { Loader2, MessageSquare, AlertCircle, ChevronRight, FileText } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  type ReviewFilter,
  reviewNeedsAction,
  sortAndFilterReviews,
} from "@/lib/employeeFormationUtils";
import { cn } from "@/lib/utils";
import {
  EmployeePageHeader,
  EmployeePageShell,
} from "@/components/employee/EmployeePageHeader";

const ANNUAL_REVIEWS_PAGE_HEADER = (
  <EmployeePageHeader
    title="Mes Entretiens"
    description="Retrouvez tous vos entretiens et suivez leur avancement"
  />
);

function ReviewsPageWrap({
  embedded,
  children,
}: {
  embedded: boolean;
  children: ReactNode;
}) {
  if (embedded) {
    return <div className="space-y-3">{children}</div>;
  }
  return (
    <EmployeePageShell>
      {ANNUAL_REVIEWS_PAGE_HEADER}
      {children}
    </EmployeePageShell>
  );
}

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

function interviewLabel(it: string | undefined) {
  if (!it) return "—";
  return INTERVIEW_TYPE_LABELS[it as InterviewType] ?? it;
}

export type EmployeeAnnualReviewsProps = {
  /** Masque le titre de page et ajoute colonnes type / PDF (vue « Ma formation »). */
  embedded?: boolean;
};

export default function EmployeeAnnualReviews({ embedded = false }: EmployeeAnnualReviewsProps) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState<ReviewFilter>("all");

  const {
    data: reviews = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["annual-reviews-me"],
    queryFn: async () => {
      const res = await getMyAnnualReviews();
      return res.data;
    },
  });

  const displayedReviews = useMemo(
    () => sortAndFilterReviews(reviews, embedded ? filter : "all"),
    [reviews, filter, embedded],
  );

  const handleRowClick = (reviewId: string) => {
    navigate(`/annual-reviews/${reviewId}`);
  };

  const handleKeyDown = (e: React.KeyboardEvent, reviewId: string) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleRowClick(reviewId);
    }
  };

  const colCount = embedded ? 5 : 3;

  if (isLoading) {
    return (
      <ReviewsPageWrap embedded={embedded}>
        <Card>
          <CardContent className="pt-6">
            <Table>
              <TableHeader>
                <TableRow>
                  {embedded && <TableHead>Type</TableHead>}
                  <TableHead>Date</TableHead>
                  <TableHead>Statut</TableHead>
                  {embedded && <TableHead>PDF signé</TableHead>}
                  {!embedded && <TableHead className="w-[50px]" />}
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell colSpan={colCount} className="h-32 text-center">
                    <div className="flex flex-col items-center justify-center gap-3">
                      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                      <p className="text-sm text-muted-foreground">
                        Chargement de vos entretiens...
                      </p>
                    </div>
                  </TableCell>
                </TableRow>
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </ReviewsPageWrap>
    );
  }

  if (isError) {
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      "Une erreur est survenue lors du chargement";
    return (
      <ReviewsPageWrap embedded={embedded}>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 rounded-md border border-destructive/20 bg-destructive/10 p-4 text-destructive">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <div className="flex-1">
                <p className="font-medium">Erreur lors du chargement</p>
                <p className="text-sm">{errorMessage}</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => refetch()} className="ml-auto">
                Réessayer
              </Button>
            </div>
          </CardContent>
        </Card>
      </ReviewsPageWrap>
    );
  }

  return (
    <ReviewsPageWrap embedded={embedded}>
      {embedded && reviews.length > 0 && (
        <div className="space-y-2">
          <p className="text-sm text-muted-foreground">
            Cliquez sur un entretien pour y répondre ou consulter le détail.
          </p>
          <div className="flex flex-wrap gap-2">
            {(
              [
                ["all", "Tous"],
                ["action", "À traiter"],
                ["closed", "Clôturés"],
              ] as const
            ).map(([value, label]) => (
              <Button
                key={value}
                type="button"
                size="sm"
                variant={filter === value ? "default" : "outline"}
                onClick={() => setFilter(value)}
              >
                {label}
              </Button>
            ))}
          </div>
        </div>
      )}

      {reviews.length === 0 ? (
        <Card>
          <CardContent className="py-12">
            <div className="flex flex-col items-center justify-center text-center">
              <MessageSquare className="mb-4 h-16 w-16 text-muted-foreground opacity-50" />
              <h3 className="mb-2 text-lg font-semibold">Aucun entretien pour le moment</h3>
              <p className="max-w-md text-sm text-muted-foreground">
                Vos entretiens apparaîtront ici une fois qu&apos;ils auront été planifiés par les RH.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          {!embedded && (
            <CardHeader>
              <CardTitle>Liste de vos entretiens</CardTitle>
            </CardHeader>
          )}
          <CardContent className={embedded ? "pt-4" : ""}>
            {embedded && filter !== "all" && displayedReviews.length === 0 && (
              <p className="mb-4 text-center text-sm text-muted-foreground">
                Aucun entretien dans cette catégorie.
              </p>
            )}
            <Table>
              <TableHeader>
                <TableRow>
                  {embedded && <TableHead>Type</TableHead>}
                  <TableHead>Date</TableHead>
                  <TableHead>Statut</TableHead>
                  {embedded && <TableHead>PDF signé</TableHead>}
                  {!embedded && <TableHead className="w-[50px]" />}
                </TableRow>
              </TableHeader>
              <TableBody>
                {displayedReviews.map((review: AnnualReview) => (
                  <TableRow
                    key={review.id}
                    className={cn(
                      "cursor-pointer transition-colors hover:bg-muted/50",
                      reviewNeedsAction(review.status) && "bg-warning/10",
                    )}
                    onClick={() => handleRowClick(review.id)}
                    role="button"
                    tabIndex={0}
                    aria-label="Voir l'entretien"
                    onKeyDown={(e) => handleKeyDown(e, review.id)}
                  >
                    {embedded && (
                      <TableCell className="max-w-[220px] text-sm">
                        {interviewLabel(review.interview_type)}
                      </TableCell>
                    )}
                    <TableCell className="text-muted-foreground">
                      {formatDate(review.planned_date)}
                    </TableCell>
                    <TableCell>
                      <AnnualReviewBadge status={review.status} compact />
                    </TableCell>
                    {embedded && (
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        {review.signed_pdf_url ? (
                          <Button variant="link" className="h-auto p-0" asChild>
                            <a href={review.signed_pdf_url} target="_blank" rel="noopener noreferrer">
                              <FileText className="mr-1 inline h-4 w-4" />
                              Ouvrir
                            </a>
                          </Button>
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </TableCell>
                    )}
                    {!embedded && (
                      <TableCell>
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </ReviewsPageWrap>
  );
}
