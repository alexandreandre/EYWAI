// frontend/src/pages/employee/AnnualReviewDetail.tsx
// Page employé : Détail d'un entretien

import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import {
  getAnnualReview,
  updateAnnualReview,
  acceptReview,
  refuseReview,
  downloadAnnualReviewPdf,
} from "@/api/annualReviews";
import type { AnnualReviewStatus } from "@/api/annualReviews";
import {
  Loader2,
  ArrowLeft,
  CheckCircle,
  X,
  AlertTriangle,
  Save,
  FileQuestion,
  AlertCircle,
  Info,
  Calendar,
  Clock,
  MessageSquare,
  UserCheck,
  FileText,
  FileDown,
  Eye,
} from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";

function formatDate(value: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleDateString("fr-FR", {
      day: "2-digit",
      month: "long",
      year: "numeric",
    });
  } catch {
    return value;
  }
}

export default function EmployeeAnnualReviewDetail() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [localNotes, setLocalNotes] = useState("");

  console.log("[AnnualReviewDetail] Composant monté avec reviewId:", reviewId);

  const {
    data: review,
    isLoading,
    isError,
    error,
  } = useQuery({
    queryKey: ["annual-review", reviewId],
    queryFn: async () => {
      if (!reviewId) {
        throw new Error("ID d'entretien manquant");
      }
      try {
        const res = await getAnnualReview(reviewId);
        console.log("[AnnualReviewDetail] Données reçues:", res.data);
        return res.data;
      } catch (err) {
        console.error("[AnnualReviewDetail] Erreur lors de la récupération:", err);
        throw err;
      }
    },
    enabled: !!reviewId,
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, notes }: { id: string; notes: string | null }) =>
      updateAnnualReview(id, { employee_preparation_notes: notes }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["annual-reviews-me"] });
      toast({
        title: "Notes enregistrées",
        description: "Vos notes ont été sauvegardées avec succès.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible d'enregistrer les notes.",
        variant: "destructive",
      });
    },
  });

  const acceptMutation = useMutation({
    mutationFn: acceptReview,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["annual-reviews-me"] });
      toast({
        title: "Entretien accepté",
        description: "Vous pouvez maintenant préparer vos notes pour l'entretien.",
        duration: 5000,
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible d'accepter l'entretien.",
        variant: "destructive",
      });
    },
  });

  const refuseMutation = useMutation({
    mutationFn: refuseReview,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["annual-reviews-me"] });
      toast({
        title: "Entretien refusé",
        description: "Votre refus a été enregistré.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de refuser l'entretien.",
        variant: "destructive",
      });
    },
  });

  useEffect(() => {
    setLocalNotes(review?.employee_preparation_notes ?? "");
  }, [review?.employee_preparation_notes]);

  const handleSaveNotes = () => {
    if (!review?.id) return;
    updateMutation.mutate({ id: review.id, notes: localNotes || null });
  };

  const handleAccept = () => {
    if (!review?.id) return;
    acceptMutation.mutate(review.id);
  };

  const handleRefuse = () => {
    if (!review?.id) return;
    refuseMutation.mutate(review.id);
  };

  console.log("[AnnualReviewDetail] État:", { isLoading, isError, review, reviewId, error });

  // Fallback de sécurité : toujours retourner quelque chose
  if (!reviewId) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/annual-reviews")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 p-4 bg-destructive/10 text-destructive border border-destructive/20 rounded-md">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <div className="flex-1">
                <p className="font-medium">ID d'entretien manquant</p>
                <p className="text-sm">L'identifiant de l'entretien n'a pas été fourni.</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate("/annual-reviews")}>
                Retour à la liste
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/annual-reviews")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <div className="flex items-center justify-center min-h-[400px]">
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            <p className="text-sm text-muted-foreground">Chargement de l'entretien...</p>
          </div>
        </div>
      </div>
    );
  }

  if (isError) {
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      (error as Error)?.message ??
      "Une erreur est survenue";
    console.error("[AnnualReviewDetail] Erreur:", error);
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/annual-reviews")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 p-4 bg-destructive/10 text-destructive border border-destructive/20 rounded-md">
              <AlertCircle className="h-5 w-5 flex-shrink-0" />
              <div className="flex-1">
                <p className="font-medium">Erreur lors du chargement</p>
                <p className="text-sm">{errorMessage}</p>
              </div>
              <Button variant="outline" size="sm" onClick={() => navigate("/annual-reviews")}>
                Retour à la liste
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!review) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/annual-reviews")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Card>
          <CardContent className="pt-12 pb-12">
            <div className="flex flex-col items-center justify-center text-center">
              <FileQuestion className="h-16 w-16 mb-4 text-muted-foreground opacity-50" />
              <h3 className="text-lg font-semibold mb-2">Entretien non trouvé</h3>
              <p className="text-sm text-muted-foreground mb-4">
                Cet entretien n'existe pas ou vous n'avez pas l'autorisation de le consulter.
              </p>
              <Button onClick={() => navigate("/annual-reviews")}>
                Retour à mes entretiens
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const statusMessages: Record<AnnualReviewStatus, string> = {
    planifie: `Votre entretien est prévu le ${formatDate(review.planned_date)}.`,
    en_attente_acceptation: `Votre entretien est prévu le ${formatDate(review.planned_date)}. Veuillez consulter les notes ci-dessous et accepter ou refuser.`,
    accepte: `Votre entretien est prévu le ${formatDate(review.planned_date)}. Préparez vos points à aborder ci-dessous.`,
    refuse: `Vous avez refusé cet entretien prévu le ${formatDate(review.planned_date)}.`,
    realise: `Votre entretien a été réalisé le ${formatDate(review.completed_date)}.`,
    cloture: "L'entretien est clôturé.",
  };

  const canAcceptOrRefuse = review.status === "en_attente_acceptation";
  const canEditNotes = review.status === "accepte";
  const hasNotesChanged = localNotes !== (review.employee_preparation_notes ?? "");
  const canDownloadPdf = review.status === "cloture";

  const handleViewPdf = async () => {
    if (!reviewId) return;
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      const url = window.URL.createObjectURL(blob);
      window.open(url, '_blank');
      // Ne pas révoquer immédiatement l'URL pour permettre l'ouverture dans un nouvel onglet
      setTimeout(() => window.URL.revokeObjectURL(url), 100);
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error?.response?.data?.detail || "Impossible d'ouvrir le PDF.",
        variant: "destructive",
      });
    }
  };

  const handleDownloadPdf = async () => {
    if (!reviewId) return;
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `entretien_${reviewId}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
      toast({
        title: "PDF téléchargé",
        description: "Le PDF de l'entretien a été téléchargé avec succès.",
      });
    } catch (error: any) {
      toast({
        title: "Erreur",
        description: error?.response?.data?.detail || "Impossible de télécharger le PDF.",
        variant: "destructive",
      });
    }
  };

  console.log("[AnnualReviewDetail] Rendu avec review:", review);
  console.log("[AnnualReviewDetail] Statut:", review.status);
  console.log("[AnnualReviewDetail] canAcceptOrRefuse:", canAcceptOrRefuse);
  console.log("[AnnualReviewDetail] canEditNotes:", canEditNotes);

  return (
    <div className="space-y-6">
      {/* Header sobre et simple */}
      <div className="flex items-start justify-between border-b pb-4">
        <div className="flex items-start gap-4 flex-1">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={() => navigate("/annual-reviews")}
            className="mt-1"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-foreground">Fiche Entretien</h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
              {review.planned_date && (
                <span>{formatDate(review.planned_date)}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canDownloadPdf && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={handleViewPdf}
                className="gap-2"
                title="Voir le PDF"
              >
                <Eye className="h-4 w-4" />
                Voir
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleDownloadPdf}
                className="gap-2"
                title="Télécharger le PDF"
              >
                <FileDown className="h-4 w-4" />
                Télécharger
              </Button>
            </>
          )}
          <AnnualReviewBadge status={review.status} />
        </div>
      </div>

      {/* Statut */}
      <Card className="border-l-4 border-l-indigo-500">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <UserCheck className="h-5 w-5 text-indigo-600" />
              Statut
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-muted rounded-lg">
                  <FileQuestion className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium">État actuel</p>
                  <p className="text-xs text-muted-foreground">{statusMessages[review.status]}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

      {/* Statut planifie - Message informatif */}
      {review.status === "planifie" && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5" />
              Prochaines étapes
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-start gap-3 p-4 bg-blue-50 dark:bg-blue-950/20 border border-blue-200 dark:border-blue-800 rounded-lg">
              <Info className="h-5 w-5 text-blue-600 dark:text-blue-400 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold text-blue-900 dark:text-blue-100 mb-1">
                  Votre entretien est planifié
                </p>
                <p className="text-sm text-blue-700 dark:text-blue-300">
                  Les RH préparent actuellement les notes de l'entretien. Vous recevrez une notification dès qu'elles seront disponibles et que vous pourrez l'accepter ou la refuser.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Statut en_attente_acceptation - Notes et boutons - Design amélioré */}
      {review.status === "en_attente_acceptation" && (
        <Card className="border-l-4 border-l-amber-500 shadow-md">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-50 dark:bg-amber-950/20 rounded-lg">
                <MessageSquare className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div className="flex-1">
                <CardTitle className="text-lg">Notes de préparation</CardTitle>
                <CardDescription className="mt-1">
                  Notes préparées par les RH. Veuillez les consulter attentivement avant d'accepter ou de refuser.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {review.rh_preparation_template ? (
              <div className="p-6 bg-gradient-to-br from-amber-50/50 to-orange-50/30 dark:from-amber-950/10 dark:to-orange-950/5 rounded-lg border border-amber-200 dark:border-amber-800">
                <div className="prose prose-sm max-w-none">
                  <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">
                    {review.rh_preparation_template}
                  </p>
                </div>
              </div>
            ) : (
              <div className="p-8 bg-muted/30 rounded-lg border-2 border-dashed border-muted-foreground/20 text-center">
                <MessageSquare className="h-12 w-12 mx-auto mb-3 text-muted-foreground/40" />
                <p className="text-sm font-medium text-muted-foreground">
                  Aucune note fournie
                </p>
              </div>
            )}
            <div className="flex flex-col sm:flex-row gap-3">
              <Button
                onClick={handleAccept}
                disabled={acceptMutation.isPending}
                className="flex-1"
                size="lg"
              >
                {acceptMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle className="mr-2 h-4 w-4" />
                )}
                Accepter l'entretien
              </Button>
              <AlertDialog>
                <AlertDialogTrigger asChild>
                  <Button
                    variant="destructive"
                    disabled={refuseMutation.isPending}
                    className="flex-1"
                    size="lg"
                  >
                    {refuseMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <X className="mr-2 h-4 w-4" />
                    )}
                    Refuser l'entretien
                  </Button>
                </AlertDialogTrigger>
                <AlertDialogContent>
                  <AlertDialogHeader>
                    <AlertDialogTitle>Refuser cet entretien ?</AlertDialogTitle>
                    <AlertDialogDescription>
                      Cette action est définitive. Vous ne pourrez plus modifier votre choix.
                      Êtes-vous sûr de vouloir refuser cet entretien ?
                    </AlertDialogDescription>
                  </AlertDialogHeader>
                  <AlertDialogFooter>
                    <AlertDialogCancel>Annuler</AlertDialogCancel>
                    <AlertDialogAction
                      onClick={handleRefuse}
                      className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    >
                      Confirmer le refus
                    </AlertDialogAction>
                  </AlertDialogFooter>
                </AlertDialogContent>
              </AlertDialog>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Statut accepte - Notes et préparation - Design amélioré */}
      {canEditNotes && (
        <>
          {review.rh_preparation_template && (
            <Card className="border-l-4 border-l-amber-500">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-amber-50 dark:bg-amber-950/20 rounded-lg">
                    <MessageSquare className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div className="flex-1">
                    <CardTitle className="text-lg">Notes</CardTitle>
                    <CardDescription className="mt-1">
                      Notes préparées par les RH pour vous guider dans votre préparation
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="p-6 bg-gradient-to-br from-amber-50/50 to-orange-50/30 dark:from-amber-950/10 dark:to-orange-950/5 rounded-lg border border-amber-200 dark:border-amber-800">
                  <div className="prose prose-sm max-w-none">
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">
                      {review.rh_preparation_template}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="border-l-4 border-l-green-500 shadow-md">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-green-50 dark:bg-green-950/20 rounded-lg">
                  <Save className="h-5 w-5 text-green-600 dark:text-green-400" />
                </div>
                <div className="flex-1">
                  <CardTitle className="text-lg">Ma préparation</CardTitle>
                  <CardDescription className="mt-1">
                    Préparez vos points à aborder, objectifs, auto-évaluation et questions pour votre manager
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Textarea
                  placeholder="Exemples de points à aborder :
• Mes réalisations et succès
• Mes objectifs futurs
• Mes besoins en formation
• Mes questions pour mon manager
• Mes perspectives d'évolution professionnelle..."
                  value={localNotes}
                  onChange={(e) => setLocalNotes(e.target.value)}
                  rows={10}
                  className="resize-none min-h-[250px] text-sm"
                />
                {hasNotesChanged && (
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <Info className="h-3 w-3" />
                    Vous avez des modifications non enregistrées
                  </p>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  onClick={handleSaveNotes}
                  disabled={updateMutation.isPending || !hasNotesChanged}
                  size="lg"
                >
                  {updateMutation.isPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="mr-2 h-4 w-4" />
                  )}
                  {hasNotesChanged ? "Enregistrer les modifications" : "Enregistré"}
                </Button>
              </div>
            </CardContent>
          </Card>
        </>
      )}

      {/* Statut refuse - Message */}
      {review.status === "refuse" && (
        <Card className="border-destructive/20 bg-destructive/10">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Entretien refusé
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-start gap-3 p-4 bg-destructive/5 rounded-lg border border-destructive/20">
              <AlertTriangle className="h-5 w-5 text-destructive flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold mb-2">Vous avez refusé cet entretien</p>
                <p className="text-sm text-muted-foreground mb-3">
                  Vous avez refusé cet entretien prévu le {formatDate(review.planned_date)}.
                  Cette décision est définitive.
                </p>
                <p className="text-sm text-muted-foreground">
                  Pour toute question ou pour demander un nouveau rendez-vous, contactez les RH.
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Statut realise - Compte-rendu */}
      {review.status === "realise" && (
        <>
          {review.meeting_report && (
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <FileQuestion className="h-5 w-5 text-primary" />
                  </div>
                  <div>
                    <CardTitle className="text-lg">Compte-rendu complet</CardTitle>
                    <CardDescription className="mt-1">
                      Compte-rendu rédigé par les RH après la réalisation de l'entretien
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-6 opacity-75">
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                      <FileQuestion className="h-4 w-4" />
                      Compte-rendu d'entretien
                    </h3>
                    <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                      {review.meeting_report}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {review.employee_preparation_notes && (
            <Card className="border-l-4 border-l-green-500">
              <CardHeader>
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-green-50 dark:bg-green-950/20 rounded-lg">
                    <Save className="h-5 w-5 text-green-600 dark:text-green-400" />
                  </div>
                  <div className="flex-1">
                    <CardTitle className="text-lg">Ma préparation</CardTitle>
                    <CardDescription className="mt-1">
                      Vos notes de préparation pour cet entretien
                    </CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="p-6 bg-gradient-to-br from-green-50/50 to-emerald-50/30 dark:from-green-950/10 dark:to-emerald-950/5 rounded-lg border border-green-200 dark:border-green-800">
                  <div className="prose prose-sm max-w-none">
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">
                      {review.employee_preparation_notes}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {!review.meeting_report && !review.employee_preparation_notes && (
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-3 p-4 bg-muted/50 rounded-lg border border-dashed">
                  <Info className="h-5 w-5 text-muted-foreground flex-shrink-0" />
                  <div>
                    <p className="font-medium mb-1">Entretien réalisé</p>
                    <p className="text-sm text-muted-foreground">
                      Le compte-rendu sera disponible une fois que les RH l'auront complété.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Statut cloture - Compte-rendu complet */}
      {review.status === "cloture" && (
        <Card className="border-l-4 border-l-primary">
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <CheckCircle className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-xl">Compte-rendu complet</CardTitle>
                  <CardDescription>
                    Résumé détaillé de votre entretien
                  </CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-6 opacity-75">
              {review.meeting_report && (
                <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <FileQuestion className="h-4 w-4" />
                    Compte-rendu d'entretien
                  </h3>
                  <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {review.meeting_report}
                  </p>
                </div>
              )}
              {review.evaluation_summary && (
                <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-primary">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <Info className="h-4 w-4" />
                    Résumé de l'évaluation
                  </h3>
                  <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {review.evaluation_summary}
                  </p>
                </div>
              )}
              
              <div className="grid md:grid-cols-2 gap-6">
                {review.objectives_achieved && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                      <CheckCircle className="h-4 w-4" />
                      Objectifs atteints
                    </h3>
                    <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                      {review.objectives_achieved}
                    </p>
                  </div>
                )}
                
                {review.objectives_next_year && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                      <ArrowLeft className="h-4 w-4 rotate-[-90deg]" />
                      Objectifs futurs
                    </h3>
                    <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                      {review.objectives_next_year}
                    </p>
                  </div>
                )}
              </div>

              {review.strengths && (
                <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <CheckCircle className="h-4 w-4" />
                    Points forts
                  </h3>
                  <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {review.strengths}
                  </p>
                </div>
              )}

              {review.improvement_areas && (
                <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <AlertTriangle className="h-4 w-4" />
                    Axes d'amélioration
                  </h3>
                  <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {review.improvement_areas}
                  </p>
                </div>
              )}

              {review.training_needs && (
                <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <Info className="h-4 w-4" />
                    Besoins en formation
                  </h3>
                  <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {review.training_needs}
                  </p>
                </div>
              )}

              {review.career_development && (
                <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <ArrowLeft className="h-4 w-4 rotate-[-45deg]" />
                    Évolution professionnelle
                  </h3>
                  <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {review.career_development}
                  </p>
                </div>
              )}

              {review.salary_review && (
                <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <CheckCircle className="h-4 w-4" />
                    Évolution salariale
                  </h3>
                  <p className="text-sm text-foreground whitespace-pre-wrap leading-relaxed">
                    {review.salary_review}
                  </p>
                </div>
              )}

              {review.overall_rating && (
                <div className="p-4 bg-primary/10 rounded-lg border border-primary/20">
                  <h3 className="font-semibold mb-2 text-base flex items-center gap-2">
                    <CheckCircle className="h-4 w-4" />
                    Note globale
                  </h3>
                  <p className="text-lg font-bold text-primary">
                    {review.overall_rating}
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
      )}
    </div>
  );
}
