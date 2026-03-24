// frontend/src/pages/employee/AnnualReviews.tsx
// Page employé : Liste de tous les entretiens

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
import { getMyAnnualReviews } from "@/api/annualReviews";
import type { AnnualReview } from "@/api/annualReviews";
import { Loader2, MessageSquare, AlertCircle, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";

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

export default function EmployeeAnnualReviews() {
  const navigate = useNavigate();

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

  const handleRowClick = (reviewId: string) => {
    console.log("[AnnualReviews] Clic sur entretien:", reviewId);
    navigate(`/annual-reviews/${reviewId}`);
  };

  const handleKeyDown = (
    e: React.KeyboardEvent,
    reviewId: string
  ) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleRowClick(reviewId);
    }
  };

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Mes Entretiens</h1>
          <p className="text-muted-foreground mt-2">
            Retrouvez tous vos entretiens et suivez leur avancement
          </p>
        </div>
        <Card>
          <CardContent className="pt-6">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Statut</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                <TableRow>
                  <TableCell colSpan={2} className="h-32 text-center">
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
      </div>
    );
  }

  if (isError) {
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } })?.response?.data
        ?.detail ?? "Une erreur est survenue lors du chargement";
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-bold">Mes Entretiens</h1>
          <p className="text-muted-foreground mt-2">
            Retrouvez tous vos entretiens et suivez leur avancement
          </p>
        </div>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 p-4 bg-destructive/10 text-destructive border border-destructive/20 rounded-md">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
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
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Mes Entretiens</h1>
        <p className="text-muted-foreground mt-2">
          Retrouvez tous vos entretiens et suivez leur avancement
        </p>
      </div>

      {reviews.length === 0 ? (
        <Card>
          <CardContent className="pt-12 pb-12">
            <div className="flex flex-col items-center justify-center text-center">
              <MessageSquare className="h-16 w-16 mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-semibold mb-2">
                Aucun entretien pour le moment
              </h3>
              <p className="text-sm text-muted-foreground max-w-md">
                Vos entretiens apparaîtront ici une fois qu'ils auront été
                planifiés par les RH.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>Liste de vos entretiens</CardTitle>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="w-[50px]"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviews.map((review: AnnualReview) => (
                  <TableRow
                    key={review.id}
                    className="cursor-pointer hover:bg-muted/50 transition-colors duration-150"
                    onClick={() => handleRowClick(review.id)}
                    role="button"
                    tabIndex={0}
                    aria-label="Voir l'entretien"
                    onKeyDown={(e) => handleKeyDown(e, review.id)}
                  >
                    <TableCell className="text-muted-foreground">
                      {formatDate(review.planned_date)}
                    </TableCell>
                    <TableCell>
                      <AnnualReviewBadge status={review.status} compact />
                    </TableCell>
                    <TableCell>
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
