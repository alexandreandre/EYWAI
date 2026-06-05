// frontend/src/pages/AnnualReviewDetail.tsx
// Page détail d'un entretien (côté RH)

import { pageTitleClassName } from '@/components/layout';
import { useParams, useNavigate, Link, useLocation } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { SharkFinLoader } from '@/components/SharkFinLoader';
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import { AnnualReviewForm } from "@/components/AnnualReviewForm";
import { AnnualReviewWorkflowStepper } from "@/components/annual-reviews/AnnualReviewWorkflowStepper";
import { AnnualReviewReadOnlySections } from "@/components/annual-reviews/AnnualReviewReadOnlySections";
import { SignatureStatusBadge } from "@/components/annual-reviews/SignatureStatusBadge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  getAnnualReview,
  updateAnnualReview,
  markAsCompleted,
  downloadAnnualReviewPdf,
  sendForSignature,
  INTERVIEW_TYPE_LABELS,
  type InterviewType,
} from "@/api/annualReviews";
import type { AnnualReviewUpdate } from "@/api/annualReviews";
import { getTemplate, getTemplates } from "@/api/interviewTemplates";
import { getEmployeePromotions } from "@/api/promotions";
import { PromotionModal } from "@/components/PromotionModal";
import { PromotionBadge } from "@/components/PromotionBadge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import apiClient from "@/api/apiClient";
import {
  formatAnnualReviewDate,
  employeeAcceptanceShortLabel,
  getReviewDateDisplay,
} from "@/lib/annualReviewLabels";
import { annualReviewFormCompletionPercent } from "@/lib/annualReviewFormUtils";
import {
  Loader2,
  ArrowLeft,
  RefreshCw,
  CheckCircle,
  FileText,
  MessageSquare,
  User,
  Edit,
  FileDown,
  Eye,
  TrendingUp,
  Plus,
  PenLine,
  ExternalLink,
  MoreHorizontal,
  Settings2,
} from "lucide-react";
import { useState, useEffect, useMemo } from "react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type EmployeeHeader = {
  id: string;
  first_name?: string | null;
  last_name?: string | null;
  job_title?: string | null;
};

function formatLongDate(value: string | null | undefined): string {
  if (!value) return "—";
  try {
    const d = value.includes("T") ? new Date(value) : new Date(`${value}T12:00:00`);
    return d.toLocaleDateString("fr-FR", {
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
  const location = useLocation();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [isEditingTemplate, setIsEditingTemplate] = useState(false);
  const [editedTemplate, setEditedTemplate] = useState("");
  const [isEditingReport, setIsEditingReport] = useState(false);
  const [promotionModalOpen, setPromotionModalOpen] = useState(false);
  const [metaDialogOpen, setMetaDialogOpen] = useState(false);
  const [metaInterviewType, setMetaInterviewType] = useState<InterviewType>("annual_performance");
  const [metaTemplateId, setMetaTemplateId] = useState<string>("");
  const [sendSigOpen, setSendSigOpen] = useState(false);
  const [clotureDialogOpen, setClotureDialogOpen] = useState(false);
  const [secondSignerEmail, setSecondSignerEmail] = useState("");
  const [expirationDays, setExpirationDays] = useState("15");
  const [activeTab, setActiveTab] = useState("preparation");

  const {
    data: review,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["annual-review", reviewId],
    queryFn: async () => {
      const res = await getAnnualReview(reviewId!);
      return res.data;
    },
    enabled: !!reviewId,
  });

  const { data: employee } = useQuery({
    queryKey: ["employee", review?.employee_id],
    queryFn: async () => {
      const res = await apiClient.get<EmployeeHeader>(`/api/employees/${review!.employee_id}`);
      return res.data;
    },
    enabled: !!review?.employee_id,
  });

  const { data: linkedTemplate } = useQuery({
    queryKey: ["interview-template", review?.template_id],
    queryFn: async () => {
      const res = await getTemplate(review!.template_id!);
      return res.data;
    },
    enabled: !!review?.template_id,
  });

  const { data: metaTemplates = [] } = useQuery({
    queryKey: ["interview-templates"],
    queryFn: async () => (await getTemplates()).data,
    enabled: metaDialogOpen,
  });

  const templatesForMetaType = useMemo(
    () =>
      metaTemplates.filter(
        (t) => t.status === "active" && t.interview_type === metaInterviewType
      ),
    [metaTemplates, metaInterviewType]
  );

  const { data: employeePromotions = [] } = useQuery({
    queryKey: ["employee-promotions", review?.employee_id],
    queryFn: async () => {
      if (!review?.employee_id) return [];
      const res = await getEmployeePromotions(review.employee_id);
      return res.data ?? [];
    },
    enabled: !!review?.employee_id,
  });

  useEffect(() => {
    if (metaDialogOpen && review) {
      const it = (review.interview_type as InterviewType | undefined) ?? "annual_performance";
      setMetaInterviewType(it);
      setMetaTemplateId(review.template_id ?? "");
    }
  }, [metaDialogOpen, review]);

  useEffect(() => {
    if (!review) return;
    if (review.status === "realise" || review.status === "cloture") {
      setActiveTab("compte-rendu");
    } else {
      setActiveTab("preparation");
    }
  }, [review?.id]);

  const linkedPromotions = useMemo(
    () =>
      reviewId && employeePromotions.length
        ? employeePromotions.filter((p) => p.performance_review_id === reviewId)
        : [],
    [reviewId, employeePromotions]
  );

  const sendSignatureMutation = useMutation({
    mutationFn: async () => {
      const days = Math.min(365, Math.max(1, parseInt(expirationDays, 10) || 15));
      await sendForSignature(reviewId!, {
        second_signer_email: secondSignerEmail.trim() || null,
        expiration_days: days,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
      queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
      setSendSigOpen(false);
      setSecondSignerEmail("");
      setExpirationDays("15");
      toast({
        title: "Demande envoyée",
        description: "La procédure Yousign a été lancée.",
      });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        (err as Error)?.message ??
        "Impossible d'envoyer la demande.";
      toast({ title: "Erreur", description: msg, variant: "destructive" });
    },
  });

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
      setIsEditingReport(true);
      setActiveTab("compte-rendu");
      toast({
        title: "Entretien marqué comme réalisé",
        description: "Vous pouvez maintenant remplir la fiche d'entretien.",
      });
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
    setIsEditingReport(false);
  };

  useEffect(() => {
    if (review?.status === "realise" && !review.meeting_report && !isEditingReport) {
      setIsEditingReport(true);
    }
  }, [review?.status, review?.meeting_report, isEditingReport]);

  const handleClose = () => {
    const fromHub = (location.state as { fromFormationHub?: boolean } | null)?.fromFormationHub;
    if (fromHub) {
      navigate({ pathname: "/formation", hash: "entretiens" });
      return;
    }
    const params = new URLSearchParams(window.location.search);
    const returnTo = params.get("returnTo");
    const employeeId = params.get("employeeId");
    const tab = params.get("tab");

    if (returnTo === "employee" && employeeId) {
      navigate(`/employees/${employeeId}${tab ? `?tab=${tab}` : ""}`);
    } else {
      navigate("/annual-reviews");
    }
  };

  const handleCloture = async () => {
    await updateMutation.mutateAsync({ status: "cloture" });
    setClotureDialogOpen(false);
    setActiveTab("pdf");
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

  const handleSaveMeta = async () => {
    if (!reviewId) return;
    await updateMutation.mutateAsync({
      interview_type: metaInterviewType,
      template_id: metaTemplateId || null,
    });
    queryClient.invalidateQueries({ queryKey: ["interview-template"] });
    setMetaDialogOpen(false);
  };

  const handleViewPdf = async () => {
    if (!reviewId) return;
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      openBlobInNewTab(blob, 100);
    } catch (error: unknown) {
      const detail =
        error &&
        typeof error === "object" &&
        "response" in error &&
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast({
        title: "Erreur",
        description: detail || "Impossible d'ouvrir le PDF.",
        variant: "destructive",
      });
    }
  };

  const handleDownloadPdf = async () => {
    if (!reviewId) return;
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      downloadBlob(blob, `entretien_${reviewId}.pdf`);
      toast({
        title: "PDF téléchargé",
        description: "Le PDF de l'entretien a été téléchargé avec succès.",
      });
    } catch (error: unknown) {
      const detail =
        error &&
        typeof error === "object" &&
        "response" in error &&
        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail;
      toast({
        title: "Erreur",
        description: detail || "Impossible de télécharger le PDF.",
        variant: "destructive",
      });
    }
  };

  if (isLoading) {
    return <SharkFinLoader variant="fullPage" label="Chargement de l'entretien…" />;
  }

  if (isError) {
    const errorMessage =
      (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
      (error as Error)?.message ??
      "Impossible de charger l'entretien.";
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={handleClose}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Card>
          <CardContent className="pt-6">
            <div className="flex flex-col items-stretch gap-4 rounded-md border border-destructive/20 bg-destructive/10 p-4 text-destructive sm:flex-row sm:items-center">
              <div className="flex-1">
                <p className="font-medium">Erreur lors du chargement de l&apos;entretien</p>
                <p className="text-sm text-muted-foreground mt-1">{errorMessage}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={isFetching}
                  onClick={() => void refetch()}
                >
                  <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
                  Réessayer
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (!review) {
    return (
      <div className="space-y-6">
        <Button variant="ghost" onClick={handleClose}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Retour
        </Button>
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">
              Entretien introuvable ou vous n&apos;avez pas l&apos;autorisation de le consulter.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const canEditForm = review.status === "realise" || review.status === "cloture";
  const canMarkCompleted = review.status === "accepte";
  const canCloture = review.status === "realise";
  const canEditRhNotes =
    review.status === "planifie" ||
    review.status === "en_attente_acceptation" ||
    review.status === "accepte";
  const canDownloadPdf = review.status === "cloture";
  const sigStatus = review.signature_status;
  const canSendForSignature =
    review.status === "cloture" &&
    (sigStatus == null || sigStatus === "" || sigStatus === "refused" || sigStatus === "expired");
  const canDownloadSignedPdf =
    review.signature_status === "signed" && !!review.signed_pdf_url;
  const showEmployeePrep =
    review.status === "accepte" || review.status === "realise" || review.status === "cloture";

  const employeeName = employee
    ? `${employee.first_name ?? ""} ${employee.last_name ?? ""}`.trim() || "Collaborateur"
    : "Collaborateur";
  const employeeInitials = employee
    ? `${employee.first_name?.charAt(0) ?? ""}${employee.last_name?.charAt(0) ?? ""}`.toUpperCase() ||
      "?"
    : "?";
  const interviewTypeLabel =
    INTERVIEW_TYPE_LABELS[(review.interview_type as InterviewType) ?? "annual_performance"];
  const dateDisplay = getReviewDateDisplay(review);
  const completionPercent = annualReviewFormCompletionPercent(review);
  const acceptanceLabel = employeeAcceptanceShortLabel(review.employee_acceptance_status);

  const employeeHref = `/employees/${review.employee_id}?tab=entretiens`;

  return (
    <div className="space-y-6">
      {/* En-tête */}
      <div className="flex flex-col gap-4 border-b pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex flex-1 items-start gap-3">
          <Button variant="ghost" size="sm" onClick={handleClose} className="mt-1 shrink-0">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <Avatar className="h-12 w-12 shrink-0">
            <AvatarFallback className="bg-primary/10 text-primary text-sm font-semibold">
              {employeeInitials}
            </AvatarFallback>
          </Avatar>
          <div className="min-w-0 flex-1">
            <h1 className={pageTitleClassName}>Fiche d&apos;entretien</h1>
            <p className="mt-1 text-lg font-medium">
              <Link to={employeeHref} className="text-primary hover:underline">
                {employeeName}
              </Link>
              {employee?.job_title ? (
                <span className="ml-2 text-sm font-normal text-muted-foreground">
                  · {employee.job_title}
                </span>
              ) : null}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
              <span>{interviewTypeLabel}</span>
              <span>·</span>
              <span>Année {review.year}</span>
              <span>·</span>
              <span>
                {dateDisplay.label} {dateDisplay.value}
              </span>
              {review.completed_date ? (
                <>
                  <span>·</span>
                  <span>Réalisé le {formatAnnualReviewDate(review.completed_date)}</span>
                </>
              ) : null}
              {linkedTemplate?.name ? (
                <>
                  <span>·</span>
                  <span>Modèle : {linkedTemplate.name}</span>
                </>
              ) : null}
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <AnnualReviewBadge status={review.status} compact />
              <SignatureStatusBadge status={review.signature_status} />
              {acceptanceLabel ? (
                <span className="text-xs text-muted-foreground">{acceptanceLabel}</span>
              ) : null}
              {review.employee_acceptance_date ? (
                <span className="text-xs text-muted-foreground">
                  le {formatLongDate(review.employee_acceptance_date)}
                </span>
              ) : null}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2 sm:justify-end">
          {canMarkCompleted && (
            <Button
              onClick={() => markCompletedMutation.mutate()}
              disabled={markCompletedMutation.isPending}
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
            <Button variant="secondary" onClick={() => setClotureDialogOpen(true)}>
              <FileText className="mr-2 h-4 w-4" />
              Clôturer
            </Button>
          )}
          {canSendForSignature && (
            <Button onClick={() => setSendSigOpen(true)}>
              <PenLine className="mr-2 h-4 w-4" />
              Envoyer pour signature
            </Button>
          )}

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="icon" aria-label="Plus d'actions">
                <MoreHorizontal className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-56">
              <DropdownMenuItem onClick={() => setMetaDialogOpen(true)}>
                <Settings2 className="mr-2 h-4 w-4" />
                Type d&apos;entretien &amp; modèle
              </DropdownMenuItem>
              <DropdownMenuItem onClick={() => setPromotionModalOpen(true)}>
                <TrendingUp className="mr-2 h-4 w-4" />
                Créer une promotion
              </DropdownMenuItem>
              {canDownloadPdf && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={handleViewPdf}>
                    <Eye className="mr-2 h-4 w-4" />
                    Voir le PDF
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={handleDownloadPdf}>
                    <FileDown className="mr-2 h-4 w-4" />
                    Télécharger le PDF
                  </DropdownMenuItem>
                </>
              )}
              {canDownloadSignedPdf && review.signed_pdf_url && (
                <DropdownMenuItem asChild>
                  <a href={review.signed_pdf_url} target="_blank" rel="noopener noreferrer">
                    <ExternalLink className="mr-2 h-4 w-4" />
                    PDF signé
                  </a>
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {/* Workflow */}
      <Card>
        <CardContent className="pt-6">
          <AnnualReviewWorkflowStepper
            status={review.status}
            signatureStatus={review.signature_status}
          />
        </CardContent>
      </Card>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid h-11 w-full grid-cols-2 sm:grid-cols-4">
          <TabsTrigger value="preparation">Préparation</TabsTrigger>
          <TabsTrigger value="compte-rendu" disabled={!canEditForm}>
            Compte-rendu
            {canEditForm ? (
              <span className="ml-1.5 text-xs text-muted-foreground">({completionPercent}%)</span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="pdf" disabled={!canDownloadPdf && !canSendForSignature}>
            PDF &amp; signature
          </TabsTrigger>
          <TabsTrigger value="promotions">
            Promotions
            {linkedPromotions.length > 0 ? (
              <span className="ml-1.5 text-xs">({linkedPromotions.length})</span>
            ) : null}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="preparation" className="mt-4 space-y-4">
          <Card>
            <CardHeader className="flex flex-row items-start justify-between gap-4">
              <div>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <MessageSquare className="h-5 w-5 text-muted-foreground" />
                  Notes de préparation RH
                </CardTitle>
                <CardDescription>
                  Visibles par le salarié pour préparer l&apos;entretien
                </CardDescription>
              </div>
              {canEditRhNotes && (
                <Button variant="outline" size="sm" onClick={handleEditTemplate}>
                  <Edit className="mr-2 h-4 w-4" />
                  Modifier
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {review.rh_preparation_template ? (
                <div className="rounded-lg border bg-muted/40 p-4">
                  <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                    {review.rh_preparation_template}
                  </p>
                </div>
              ) : (
                <div className="rounded-lg border border-dashed bg-muted/30 p-8 text-center">
                  <MessageSquare className="mx-auto mb-3 h-10 w-10 text-muted-foreground/40" />
                  <p className="text-sm font-medium text-muted-foreground">Aucune note définie</p>
                  {canEditRhNotes && (
                    <Button variant="outline" size="sm" className="mt-4" onClick={handleEditTemplate}>
                      <Edit className="mr-2 h-4 w-4" />
                      Ajouter des notes
                    </Button>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {showEmployeePrep && (
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <User className="h-5 w-5 text-muted-foreground" />
                  Préparation du salarié
                </CardTitle>
                <CardDescription>
                  {review.employee_preparation_validated_at
                    ? `Validée le ${formatLongDate(review.employee_preparation_validated_at)}`
                    : "Notes et retour du collaborateur"}
                  {acceptanceLabel ? ` · ${acceptanceLabel}` : ""}
                  {review.employee_acceptance_date
                    ? ` (${formatLongDate(review.employee_acceptance_date)})`
                    : ""}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {review.employee_preparation_notes ? (
                  <div className="rounded-lg border bg-muted/40 p-4">
                    <p className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
                      {review.employee_preparation_notes}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm italic text-muted-foreground">
                    Le salarié n&apos;a pas encore ajouté de notes de préparation.
                  </p>
                )}
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="compte-rendu" className="mt-4">
          {canEditForm ? (
            <Card>
              <CardHeader className="flex flex-row items-start justify-between gap-4 border-b">
                <div>
                  <CardTitle className="text-xl">Compte-rendu complet</CardTitle>
                  <CardDescription>
                    {isEditingReport
                      ? "Remplissez la fiche — les sections vides restent visibles en lecture"
                      : review.status === "cloture"
                        ? "Entretien clôturé"
                        : `${completionPercent} % complété`}
                  </CardDescription>
                </div>
                {!isEditingReport && (
                  <Button variant="outline" size="sm" onClick={() => setIsEditingReport(true)}>
                    <Edit className="mr-2 h-4 w-4" />
                    Modifier
                  </Button>
                )}
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
                  <AnnualReviewReadOnlySections review={review} />
                )}
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                Le compte-rendu sera disponible une fois l&apos;entretien marqué comme réalisé.
              </CardContent>
            </Card>
          )}
        </TabsContent>

        <TabsContent value="pdf" className="mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">PDF et signature électronique</CardTitle>
              <CardDescription>
                Disponibles après clôture de l&apos;entretien
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {canDownloadPdf ? (
                <div className="flex flex-wrap gap-2">
                  <Button variant="outline" onClick={handleViewPdf}>
                    <Eye className="mr-2 h-4 w-4" />
                    Voir le PDF
                  </Button>
                  <Button variant="outline" onClick={handleDownloadPdf}>
                    <FileDown className="mr-2 h-4 w-4" />
                    Télécharger
                  </Button>
                  {canSendForSignature && (
                    <Button onClick={() => setSendSigOpen(true)}>
                      <PenLine className="mr-2 h-4 w-4" />
                      Envoyer pour signature
                    </Button>
                  )}
                  {canDownloadSignedPdf && review.signed_pdf_url && (
                    <Button variant="outline" asChild>
                      <a href={review.signed_pdf_url} target="_blank" rel="noopener noreferrer">
                        <ExternalLink className="mr-2 h-4 w-4" />
                        PDF signé
                      </a>
                    </Button>
                  )}
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Clôturez l&apos;entretien pour générer le PDF et lancer la signature Yousign.
                </p>
              )}
              {review.signature_status ? (
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-muted-foreground">Statut signature :</span>
                  <SignatureStatusBadge status={review.signature_status} />
                </div>
              ) : null}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="promotions" className="mt-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 text-lg">
                  <TrendingUp className="h-5 w-5 text-muted-foreground" />
                  Promotions liées
                </CardTitle>
                <CardDescription>
                  Évolutions créées à partir de cet entretien
                </CardDescription>
              </div>
              <Button size="sm" onClick={() => setPromotionModalOpen(true)}>
                <Plus className="mr-2 h-4 w-4" />
                Créer une promotion
              </Button>
            </CardHeader>
            <CardContent>
              {linkedPromotions.length === 0 ? (
                <p className="py-4 text-sm text-muted-foreground">
                  Aucune promotion liée à cet entretien.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Évolution</TableHead>
                      <TableHead>Date d&apos;effet</TableHead>
                      <TableHead>Statut</TableHead>
                      <TableHead className="w-[80px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {linkedPromotions.map((promo) => {
                      const evolutionText =
                        [
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
                          onClick={() =>
                            navigate(
                              `/promotions/${promo.id}?returnTo=annual-review&reviewId=${reviewId}`
                            )
                          }
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
                              onClick={() =>
                                navigate(
                                  `/promotions/${promo.id}?returnTo=annual-review&reviewId=${reviewId}`
                                )
                              }
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
        </TabsContent>
      </Tabs>

      <AlertDialog open={clotureDialogOpen} onOpenChange={setClotureDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Clôturer cet entretien ?</AlertDialogTitle>
            <AlertDialogDescription>
              La fiche passera au statut « Clôturé » et un PDF de synthèse sera généré. Vérifiez
              que le compte-rendu est complet ({completionPercent} % renseigné).
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => void handleCloture()}
              disabled={updateMutation.isPending}
            >
              {updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Clôturer et générer le PDF
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={metaDialogOpen} onOpenChange={setMetaDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Type d&apos;entretien et modèle</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Type d&apos;entretien *</Label>
              <Select
                value={metaInterviewType}
                onValueChange={(v) => {
                  setMetaInterviewType(v as InterviewType);
                  setMetaTemplateId("");
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {(Object.keys(INTERVIEW_TYPE_LABELS) as InterviewType[]).map((k) => (
                    <SelectItem key={k} value={k}>
                      {INTERVIEW_TYPE_LABELS[k]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label>Modèle de trame (optionnel)</Label>
              <Select
                value={metaTemplateId || "_none"}
                onValueChange={(v) => setMetaTemplateId(v === "_none" ? "" : v)}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Aucun" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">Aucun modèle</SelectItem>
                  {templatesForMetaType.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMetaDialogOpen(false)}>
              Annuler
            </Button>
            <Button onClick={handleSaveMeta} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={sendSigOpen} onOpenChange={setSendSigOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>Envoyer pour signature électronique</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            Un PDF sera envoyé via Yousign au salarié. Vous pouvez ajouter un second signataire
            (ordre séquentiel).
          </p>
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="second-signer-email">E-mail second signataire (optionnel)</Label>
              <Input
                id="second-signer-email"
                type="email"
                placeholder="rh@exemple.fr"
                value={secondSignerEmail}
                onChange={(e) => setSecondSignerEmail(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="expiration-days">Délai d&apos;expiration (jours)</Label>
              <Input
                id="expiration-days"
                type="number"
                min={1}
                max={365}
                value={expirationDays}
                onChange={(e) => setExpirationDays(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setSendSigOpen(false)}>
              Annuler
            </Button>
            <Button
              onClick={() => sendSignatureMutation.mutate()}
              disabled={sendSignatureMutation.isPending}
            >
              {sendSignatureMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : null}
              Confirmer l&apos;envoi
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isEditingTemplate} onOpenChange={setIsEditingTemplate}>
        <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Modifier les notes de préparation</DialogTitle>
          </DialogHeader>
          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="template-textarea">Notes (visibles par le salarié)</Label>
              <Textarea
                id="template-textarea"
                placeholder="Objectifs, points à aborder, documents à préparer..."
                value={editedTemplate}
                onChange={(e) => setEditedTemplate(e.target.value)}
                rows={10}
                className="min-h-[250px] resize-none"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditingTemplate(false)}>
              Annuler
            </Button>
            <Button onClick={handleSaveTemplate} disabled={updateMutation.isPending}>
              {updateMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Enregistrer
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <PromotionModal
        isOpen={promotionModalOpen}
        onClose={() => setPromotionModalOpen(false)}
        promotion={null}
        initialEmployeeId={review.employee_id}
        initialPerformanceReviewId={reviewId ?? undefined}
        onSuccess={() => {
          queryClient.invalidateQueries({
            queryKey: ["employee-promotions", review.employee_id],
          });
          queryClient.invalidateQueries({ queryKey: ["annual-review", reviewId] });
          setPromotionModalOpen(false);
        }}
      />
    </div>
  );
}
