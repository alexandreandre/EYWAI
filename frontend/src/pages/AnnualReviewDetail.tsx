// frontend/src/pages/AnnualReviewDetail.tsx
// Page détail d'un entretien (côté RH)

import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import { AnnualReviewForm } from "@/components/AnnualReviewForm";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  getAnnualReview,
  updateAnnualReview,
  markAsCompleted,
  downloadAnnualReviewPdf,
} from "@/api/annualReviews";
import type { AnnualReviewUpdate } from "@/api/annualReviews";
import { getEmployeePromotions } from "@/api/promotions";
import { PromotionModal } from "@/components/PromotionModal";
import { PromotionBadge } from "@/components/PromotionBadge";
import { Loader2, ArrowLeft, CheckCircle, Play, FileText, Info, MessageSquare, User, Edit, Calendar, Clock, UserCheck, FileCheck, FileDown, Eye, TrendingUp, Plus } from "lucide-react";
import { useState, useEffect, useMemo } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

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

export default function AnnualReviewDetail() {
  const { reviewId } = useParams<{ reviewId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isEditingTemplate, setIsEditingTemplate] = useState(false);
  const [editedTemplate, setEditedTemplate] = useState("");
  const [isEditingReport, setIsEditingReport] = useState(false);
  const [promotionModalOpen, setPromotionModalOpen] = useState(false);

  const {
    data: review,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["annual-review", reviewId],
    queryFn: async () => {
      const res = await getAnnualReview(reviewId!);
      return res.data;
    },
    enabled: !!reviewId,
  });

  const { data: employeePromotions = [] } = useQuery({
    queryKey: ["employee-promotions", review?.employee_id],
    queryFn: async () => {
      if (!review?.employee_id) return [];
      const res = await getEmployeePromotions(review.employee_id);
      return res.data ?? [];
    },
    enabled: !!review?.employee_id,
  });

  const linkedPromotions = useMemo(
    () =>
      reviewId && employeePromotions.length
        ? employeePromotions.filter((p) => p.performance_review_id === reviewId)
        : [],
    [reviewId, employeePromotions]
  );

  const updateMutation = useMutation({
    mutationFn: (data: AnnualReviewUpdate) => updateAnnualReview(reviewId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
      toast({ title: "Fiche mise à jour", description: "Les modifications ont été enregistrées." });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de mettre à jour la fiche.",
        variant: "destructive",
      });
    },
  });


  const markCompletedMutation = useMutation({
    mutationFn: () => markAsCompleted(reviewId!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
      // Ouvrir automatiquement le formulaire de compte-rendu
      setIsEditingReport(true);
      toast({ title: "Entretien marqué comme réalisé", description: "Vous pouvez maintenant remplir la fiche d'entretien." });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de marquer l'entretien comme réalisé.",
        variant: "destructive",
      });
    },
  });

  const handleSaveForm = async (data: AnnualReviewUpdate) => {
    await updateMutation.mutateAsync(data);
    setIsEditingReport(false); // Passer en mode lecture seule après sauvegarde
  };

  // Ouvrir automatiquement le formulaire quand l'entretien passe au statut "realise" sans compte-rendu
  useEffect(() => {
    if (review?.status === "realise" && !review.meeting_report && !isEditingReport) {
      setIsEditingReport(true);
    }
  }, [review?.status, review?.meeting_report, isEditingReport]);

  const handleClose = () => {
    // Vérifier si on vient de EmployeeDetail
    const params = new URLSearchParams(window.location.search);
    const returnTo = params.get('returnTo');
    const employeeId = params.get('employeeId');
    const tab = params.get('tab');
    
    if (returnTo === 'employee' && employeeId) {
      // Retourner à EmployeeDetail avec l'onglet Entretiens actif
      navigate(`/employees/${employeeId}${tab ? `?tab=${tab}` : ''}`);
    } else {
      navigate("/annual-reviews");
    }
  };

  const handleCloture = async () => {
    await updateMutation.mutateAsync({ status: "cloture" });
  };

  const handleEditTemplate = () => {
    setEditedTemplate(review?.rh_preparation_template || "");
    setIsEditingTemplate(true);
  };

  const handleSaveTemplate = async () => {
    if (!reviewId) return;
    await updateMutation.mutateAsync({
      rh_preparation_template: editedTemplate || null,
    });
    setIsEditingTemplate(false);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !review) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={() => navigate("/annual-reviews")}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Card>
          <CardContent className="pt-6">
            <p className="text-destructive">Erreur lors du chargement de l'entretien.</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const canEditForm = review.status === "realise" || review.status === "cloture";
  const canMarkCompleted = review.status === "accepte";
  const canCloture = review.status === "realise";
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

  return (
    <div className="space-y-6">
      {/* Header sobre et simple */}
      <div className="flex items-start justify-between border-b pb-4">
        <div className="flex items-start gap-4 flex-1">
          <Button 
            variant="ghost" 
            size="sm"
            onClick={handleClose}
            className="mt-1"
          >
            <ArrowLeft className="h-4 w-4 mr-2" />
            Retour
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-semibold text-foreground">Fiche d'entretien</h1>
            <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
              {review.planned_date && (
                <span>{formatDate(review.planned_date)}</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPromotionModalOpen(true)}
            className="gap-2"
            title="Créer une promotion liée à cet entretien"
          >
            <TrendingUp className="h-4 w-4" />
            Créer une promotion
          </Button>
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

      {/* Barre d'actions rapides */}
      {(canMarkCompleted || canCloture) && (
        <Card className="border-l-4 border-l-primary">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <CheckCircle className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <p className="font-semibold">Actions disponibles</p>
                  <p className="text-sm text-muted-foreground">
                    {canMarkCompleted && "Marquez l'entretien comme réalisé pour commencer à remplir la fiche"}
                    {canCloture && "Clôturez l'entretien une fois la fiche complétée"}
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                {canMarkCompleted && (
                  <Button
                    onClick={() => markCompletedMutation.mutate()}
                    disabled={markCompletedMutation.isPending}
                    size="lg"
                  >
                    {markCompletedMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <CheckCircle className="mr-2 h-4 w-4" />
                    )}
                    Marquer comme réalisé
                  </Button>
                )}
                {canCloture && (
                  <Button
                    variant="secondary"
                    onClick={handleCloture}
                    disabled={updateMutation.isPending}
                    size="lg"
                  >
                    <FileText className="mr-2 h-4 w-4" />
                    Cloturer et générer le pdf
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Statut et workflow */}
      <Card className="border-l-4 border-l-indigo-500">
          <CardHeader className="pb-3">
            <CardTitle className="flex items-center gap-2 text-base">
              <UserCheck className="h-5 w-5 text-indigo-600" />
              Statut et workflow
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-muted rounded-lg">
                  <FileCheck className="h-5 w-5 text-muted-foreground" />
                </div>
                <div className="flex-1">
                  <p className="text-sm text-muted-foreground">
                    {review.status === "planifie" && "L'entretien est planifié."}
                    {review.status === "en_attente_acceptation" && "En attente de l'acceptation de l'employé"}
                    {review.status === "accepte" && "Accepté par l'employé. Prêt à être réalisé."}
                    {review.status === "refuse" && "Refusé par l'employé."}
                    {review.status === "realise" && "Entretien réalisé. Fiche à compléter."}
                    {review.status === "cloture" && "Entretien clôturé."}
                  </p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

      {/* Promotions liées à cet entretien */}
      <Card className="border-l-4 border-l-emerald-500">
        <CardHeader className="flex flex-row justify-between items-center">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-emerald-50 dark:bg-emerald-950/20 rounded-lg">
              <TrendingUp className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
            </div>
            <div>
              <CardTitle className="text-lg">Promotions liées</CardTitle>
              <CardDescription className="mt-0.5">
                Promotions créées à partir de cet entretien annuel
              </CardDescription>
            </div>
          </div>
          <Button size="sm" onClick={() => setPromotionModalOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            Créer une promotion
          </Button>
        </CardHeader>
        <CardContent>
          {linkedPromotions.length === 0 ? (
            <p className="text-sm text-muted-foreground py-4">
              Aucune promotion liée à cet entretien.
            </p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Évolution</TableHead>
                  <TableHead>Date d'effet</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="w-[80px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {linkedPromotions.map((promo) => {
                  const evolutionText = [
                    promo.new_job_title,
                    promo.new_salary
                      ? `${promo.new_salary.valeur?.toLocaleString("fr-FR")} ${promo.new_salary.devise || "EUR"}`
                      : null,
                    promo.new_statut,
                  ]
                    .filter(Boolean)
                    .join(" • ") || "—";
                  return (
                    <TableRow
                      key={promo.id}
                      className="cursor-pointer hover:bg-muted/50"
                      onClick={() => navigate(`/promotions/${promo.id}?returnTo=annual-review&reviewId=${reviewId}`)}
                    >
                      <TableCell>
                        <PromotionBadge type={promo.promotion_type} variant="type" compact />
                      </TableCell>
                      <TableCell className="text-muted-foreground">{evolutionText}</TableCell>
                      <TableCell className="text-muted-foreground">
                        {new Date(promo.effective_date).toLocaleDateString("fr-FR", {
                          day: "2-digit",
                          month: "short",
                          year: "numeric",
                        })}
                      </TableCell>
                      <TableCell>
                        <PromotionBadge status={promo.status} compact />
                      </TableCell>
                      <TableCell onClick={(e) => e.stopPropagation()}>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-8 w-8 p-0"
                          onClick={() => navigate(`/promotions/${promo.id}?returnTo=annual-review&reviewId=${reviewId}`)}
                          title="Voir la promotion"
                        >
                          <Eye className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Section Notes RH - Design amélioré */}
      <Card className="border-l-4 border-l-amber-500">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-50 dark:bg-amber-950/20 rounded-lg">
                <MessageSquare className="h-5 w-5 text-amber-600 dark:text-amber-400" />
              </div>
              <div>
                <CardTitle className="text-lg">Notes de préparation</CardTitle>
                <CardDescription className="mt-1">
                  Notes visibles par l'employé pour préparer l'entretien
                </CardDescription>
              </div>
            </div>
            {review.status === "en_attente_acceptation" && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleEditTemplate}
                className="shrink-0"
              >
                <Edit className="h-4 w-4 mr-2" />
                Modifier
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
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
              <p className="text-sm font-medium text-muted-foreground mb-1">
                Aucune note définie
              </p>
              <p className="text-xs text-muted-foreground mb-4">
                Les notes aident l'employé à préparer l'entretien
              </p>
              {review.status === "en_attente_acceptation" && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleEditTemplate}
                >
                  <Edit className="h-4 w-4 mr-2" />
                  Ajouter des notes
                </Button>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Dialog pour éditer les notes */}
      <Dialog open={isEditingTemplate} onOpenChange={setIsEditingTemplate}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Modifier les notes</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="template-textarea">
                Notes (visibles par l'employé)
              </Label>
              <Textarea
                id="template-textarea"
                placeholder="Rédigez ici vos notes pour l'entretien. Ces notes seront visibles par l'employé qui pourra l'accepter ou la refuser.

Exemples de points à inclure :
• Objectifs de l'entretien
• Points à aborder
• Documents à préparer
• Questions à réfléchir en amont..."
                value={editedTemplate}
                onChange={(e) => setEditedTemplate(e.target.value)}
                rows={10}
                className="resize-none min-h-[250px]"
              />
              <p className="text-xs text-muted-foreground">
                Ces notes seront visibles par l'employé qui pourra accepter ou refuser l'entretien.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditingTemplate(false)}>
              Annuler
            </Button>
            <Button
              onClick={handleSaveTemplate}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>


      {/* Préparation employé - Design amélioré */}
      {(review.status === "accepte" || review.status === "realise" || review.status === "cloture") && (
        <Card className="border-l-4 border-l-green-500">
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-50 dark:bg-green-950/20 rounded-lg">
                <User className="h-5 w-5 text-green-600 dark:text-green-400" />
              </div>
              <div className="flex-1">
                <CardTitle className="text-lg">Préparation de l'employé</CardTitle>
                <CardDescription className="mt-1">
                  {review.employee_preparation_validated_at
                    ? `Validée le ${formatDate(review.employee_preparation_validated_at)}`
                    : "Notes de préparation de l'employé"}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {review.employee_preparation_notes ? (
              <div className="p-6 bg-gradient-to-br from-green-50/50 to-emerald-50/30 dark:from-green-950/10 dark:to-emerald-950/5 rounded-lg border border-green-200 dark:border-green-800">
                <div className="prose prose-sm max-w-none">
                  <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">
                    {review.employee_preparation_notes}
                  </p>
                </div>
              </div>
            ) : (
              <div className="p-6 bg-muted/30 rounded-lg border border-dashed text-center">
                <p className="text-sm text-muted-foreground italic">
                  L'employé n'a pas encore ajouté de notes de préparation.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Compte-rendu complet - Unifié pour realise et cloture */}
      {canEditForm && (
        <Card className="border-l-4 border-l-primary">
          <CardHeader className="border-b">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-primary/10 rounded-lg">
                  <FileText className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <CardTitle className="text-xl">Compte-rendu complet</CardTitle>
                  <CardDescription className="mt-1">
                    {isEditingReport 
                      ? "Remplissez la fiche complète de l'entretien"
                      : review.status === "cloture" 
                        ? "Entretien clôturé — Lecture seule"
                        : "Fiche d'entretien complète"}
                  </CardDescription>
                </div>
              </div>
              {!isEditingReport && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setIsEditingReport(true)}
                >
                  <Edit className="h-4 w-4 mr-2" />
                  Modifier
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="pt-6">
            {isEditingReport ? (
              <AnnualReviewForm
                review={review}
                onSave={handleSaveForm}
                onClose={() => setIsEditingReport(false)}
                isLoading={updateMutation.isPending}
              />
            ) : (
              <div className="space-y-6 opacity-75">
                {review.meeting_report && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      Compte-rendu d'entretien
                    </h3>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.meeting_report}</p>
                  </div>
                )}
                {review.evaluation_summary && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <Info className="h-4 w-4" />
                      Résumé de l'évaluation
                    </h3>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.evaluation_summary}</p>
                  </div>
                )}
                <div className="grid md:grid-cols-2 gap-4">
                  {review.objectives_achieved && (
                    <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                      <h3 className="font-semibold mb-2 flex items-center gap-2">
                        <CheckCircle className="h-4 w-4" />
                        Objectifs atteints
                      </h3>
                      <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.objectives_achieved}</p>
                    </div>
                  )}
                  {review.objectives_next_year && (
                    <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                      <h3 className="font-semibold mb-2 flex items-center gap-2">
                        <Calendar className="h-4 w-4" />
                        Objectifs futurs
                      </h3>
                      <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.objectives_next_year}</p>
                    </div>
                  )}
                </div>
                {review.strengths && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <CheckCircle className="h-4 w-4" />
                      Points forts
                    </h3>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.strengths}</p>
                  </div>
                )}
                {review.improvement_areas && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <Info className="h-4 w-4" />
                      Axes d'amélioration
                    </h3>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.improvement_areas}</p>
                  </div>
                )}
                {review.training_needs && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <Info className="h-4 w-4" />
                      Besoins en formation
                    </h3>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.training_needs}</p>
                  </div>
                )}
                {review.career_development && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <User className="h-4 w-4" />
                      Évolution professionnelle
                    </h3>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.career_development}</p>
                  </div>
                )}
                {review.salary_review && (
                  <div className="p-4 bg-muted/30 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <FileText className="h-4 w-4" />
                      Évolution salariale
                    </h3>
                    <p className="text-sm whitespace-pre-wrap leading-relaxed text-foreground">{review.salary_review}</p>
                  </div>
                )}
                {review.overall_rating && (
                  <div className="p-4 bg-primary/10 rounded-lg border-l-4 border-l-primary">
                    <h3 className="font-semibold mb-2 flex items-center gap-2">
                      <CheckCircle className="h-4 w-4" />
                      Note globale
                    </h3>
                    <p className="text-2xl font-bold text-primary">{review.overall_rating}</p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <PromotionModal
        isOpen={promotionModalOpen}
        onClose={() => setPromotionModalOpen(false)}
        promotion={null}
        initialEmployeeId={review.employee_id}
        initialPerformanceReviewId={reviewId ?? undefined}
        onSuccess={() => {
          queryClient.invalidateQueries({ queryKey: ["employee-promotions", review.employee_id] });
          queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
          setPromotionModalOpen(false);
        }}
      />
    </div>
  );
}
