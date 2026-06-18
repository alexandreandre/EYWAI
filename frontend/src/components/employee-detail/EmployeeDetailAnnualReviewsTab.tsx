import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAnnualReview,
  deleteAnnualReview,
  downloadAnnualReviewPdf,
  getEmployeeAnnualReviews,
  INTERVIEW_TYPE_LABELS,
  type AnnualReview,
  type AnnualReviewStatus,
  type InterviewType,
} from "@/api/annualReviews";
import { getTemplates } from "@/api/interviewTemplates";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/hooks/use-toast";
import {
  canRhDeleteAnnualReview,
  countOverdueActionableReviews,
  countReviewsByStatus,
  employeeAcceptanceShortLabel,
  filterReviewsForDisplay,
  findExistingReviewSameTypeYear,
  formatAnnualReviewDate,
  getNextActionableReview,
  getReviewDateDisplay,
  getReviewYearOptions,
  groupHistoricalReviewsByYear,
  interviewTypeLabel,
  interviewTypeShortLabel,
  isAnnualReviewOverdue,
  isActionableAnnualReviewStatus,
  signatureStatusShortLabel,
  sortActionableReviews,
  sortReviewsForDisplay,
} from "@/lib/annualReviewLabels";
import { cn } from "@/lib/utils";
import { useCompany } from "@/contexts/CompanyContext";
import { downloadAnnualReviewPdfFile, previewAnnualReviewPdf } from '@/lib/annualReviewPdf';
import {
  ChevronRight,
  ExternalLink,
  Eye,
  FileDown,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Trash2,
} from "lucide-react";

const STATUS_FILTER_OPTIONS: { value: AnnualReviewStatus | "all"; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "planifie", label: "Planifié" },
  { value: "en_attente_acceptation", label: "Attente acceptation" },
  { value: "accepte", label: "Accepté" },
  { value: "refuse", label: "Refusé" },
  { value: "realise", label: "Réalisé" },
  { value: "cloture", label: "Clôturé" },
];

export function annualReviewsEmployeeQueryKey(employeeId: string) {
  return ["annual-reviews", "employee", employeeId] as const;
}

export interface EmployeeDetailAnnualReviewsTabProps {
  employeeId: string;
  employeeName?: string;
  canDeleteReview?: boolean;
  onEmployeeRefresh?: () => void | Promise<void>;
}

function TableSkeleton() {
  return (
    <div className="space-y-2">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

function reviewDetailPath(reviewId: string, employeeId: string) {
  return `/annual-reviews/${reviewId}?returnTo=employee&employeeId=${employeeId}&tab=entretiens`;
}

function ReviewExtraMeta({ review }: { review: AnnualReview }) {
  const sigShort = signatureStatusShortLabel(review.signature_status);
  const acceptanceShort = employeeAcceptanceShortLabel(review.employee_acceptance_status);

  if (!sigShort && !acceptanceShort && review.status !== "refuse") return null;

  return (
    <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[10px] text-muted-foreground">
      {sigShort && <span>{sigShort}</span>}
      {acceptanceShort && <span>{acceptanceShort}</span>}
      {review.status === "refuse" && !acceptanceShort && (
        <span className="text-destructive">Refusé</span>
      )}
    </div>
  );
}

function ReviewDeleteButton({
  review,
  canDelete,
  deleting,
  onDelete,
}: {
  review: AnnualReview;
  canDelete: boolean;
  deleting: boolean;
  onDelete: (id: string) => void;
}) {
  if (!canDelete || !canRhDeleteAnnualReview(review.status)) return null;

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0 text-destructive hover:text-destructive shrink-0"
          title="Supprimer"
          aria-label="Supprimer"
          onClick={(e) => e.stopPropagation()}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Supprimer cet entretien ?</AlertDialogTitle>
          <AlertDialogDescription>Action irréversible.</AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Annuler</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => onDelete(review.id)}
            className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
            disabled={deleting}
          >
            {deleting ? <Loader2 className="h-4 w-4 animate-spin" /> : "Supprimer"}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

function HistoricalReviewRow({
  review,
  employeeId,
  canDeleteReview,
  deletingReviewId,
  onNavigate,
  onDelete,
  renderPdfActions,
}: {
  review: AnnualReview;
  employeeId: string;
  canDeleteReview: boolean;
  deletingReviewId: string | null;
  onNavigate: (path: string) => void;
  onDelete: (id: string) => void;
  renderPdfActions: (review: AnnualReview) => React.ReactNode;
}) {
  const sigShort = signatureStatusShortLabel(review.signature_status);
  const dateInfo = getReviewDateDisplay(review);

  return (
    <TableRow
      className="cursor-pointer hover:bg-muted/50"
      onClick={() => onNavigate(reviewDetailPath(review.id, employeeId))}
    >
      <TableCell
        className="py-2 text-sm max-w-[120px] truncate"
        title={interviewTypeLabel(review.interview_type)}
      >
        {interviewTypeShortLabel(review.interview_type)}
      </TableCell>
      <TableCell className="py-2 text-sm text-muted-foreground">{review.year}</TableCell>
      <TableCell className="py-2 text-sm text-muted-foreground tabular-nums">
        <span className="block text-[10px] text-muted-foreground/80">{dateInfo.label}</span>
        {dateInfo.value}
      </TableCell>
      <TableCell className="py-2">
        <div className="flex flex-wrap items-center gap-1">
          <AnnualReviewBadge status={review.status} compact />
          {sigShort && <span className="text-[10px] text-muted-foreground">{sigShort}</span>}
        </div>
      </TableCell>
      <TableCell className="py-2 text-right" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-end gap-0.5">
          {renderPdfActions(review)}
          <ReviewDeleteButton
            review={review}
            canDelete={canDeleteReview}
            deleting={deletingReviewId === review.id}
            onDelete={onDelete}
          />
          <ChevronRight className="h-4 w-4 text-muted-foreground/60 ml-0.5" />
        </div>
      </TableCell>
    </TableRow>
  );
}

export function EmployeeDetailAnnualReviewsTab({
  employeeId,
  employeeName,
  canDeleteReview = false,
  onEmployeeRefresh,
}: EmployeeDetailAnnualReviewsTabProps) {
  const navigate = useNavigate();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";

  const reviewsQuery = useQuery({
    queryKey: annualReviewsEmployeeQueryKey(employeeId),
    queryFn: async () => {
      const res = await getEmployeeAnnualReviews(employeeId);
      return res.data ?? [];
    },
    enabled: !!employeeId,
  });

  const reviews = reviewsQuery.data ?? [];
  const sorted = useMemo(() => sortReviewsForDisplay(reviews), [reviews]);
  const actionableReviews = useMemo(() => sortActionableReviews(reviews), [reviews]);
  const statusCounts = useMemo(() => countReviewsByStatus(reviews), [reviews]);
  const overdueCount = useMemo(() => countOverdueActionableReviews(reviews), [reviews]);
  const nextReview = useMemo(() => getNextActionableReview(reviews), [reviews]);
  const actionableIds = useMemo(
    () => new Set(actionableReviews.map((r) => r.id)),
    [actionableReviews],
  );
  const yearOptions = useMemo(() => getReviewYearOptions(reviews), [reviews]);

  const otherActionableReviews = useMemo(() => {
    if (!nextReview) return actionableReviews;
    return actionableReviews.filter((r) => r.id !== nextReview.id);
  }, [actionableReviews, nextReview]);

  const [filterYear, setFilterYear] = useState<number | "all">("all");
  const [filterStatus, setFilterStatus] = useState<AnnualReviewStatus | "all">("all");
  const [hideClosed, setHideClosed] = useState(true);

  const historicalReviews = useMemo(
    () =>
      filterReviewsForDisplay(
        sorted.filter((r) => !actionableIds.has(r.id)),
        { year: filterYear, status: filterStatus, hideClosed },
      ),
    [sorted, actionableIds, filterYear, filterStatus, hideClosed],
  );

  const historicalGrouped = useMemo(
    () => groupHistoricalReviewsByYear(historicalReviews),
    [historicalReviews],
  );

  const [planningModalOpen, setPlanningModalOpen] = useState(false);
  const [planningDate, setPlanningDate] = useState("");
  const [planningInterviewType, setPlanningInterviewType] =
    useState<InterviewType>("annual_performance");
  const [planningTemplateId, setPlanningTemplateId] = useState("");
  const [planningRhNotes, setPlanningRhNotes] = useState("");
  const [deletingReviewId, setDeletingReviewId] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();
  const planTypeHandled = useRef(false);

  const planningTargetYear = useMemo(() => {
    if (planningDate) return new Date(planningDate).getFullYear();
    return new Date().getFullYear();
  }, [planningDate]);

  const duplicateTypeYearReview = useMemo(
    () =>
      findExistingReviewSameTypeYear(reviews, planningInterviewType, planningTargetYear),
    [reviews, planningInterviewType, planningTargetYear],
  );

  const templatesQuery = useQuery({
    queryKey: ["interview-templates", activeCompanyId],
    queryFn: async () => {
      const res = await getTemplates();
      return res.data;
    },
    enabled: !!activeCompanyId && planningModalOpen,
  });

  const templatesForType = useMemo(
    () =>
      (templatesQuery.data ?? []).filter(
        (t) => t.status === "active" && t.interview_type === planningInterviewType,
      ),
    [templatesQuery.data, planningInterviewType],
  );

  useEffect(() => {
    const planType = searchParams.get("planType");
    if (!planType || planTypeHandled.current) return;
    if (!(planType in INTERVIEW_TYPE_LABELS)) return;
    planTypeHandled.current = true;
    setPlanningInterviewType(planType as InterviewType);
    setPlanningModalOpen(true);
    const next = new URLSearchParams(searchParams);
    next.delete("planType");
    setSearchParams(next, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    if (!planningModalOpen || templatesForType.length !== 1) return;
    const only = templatesForType[0];
    if (only && planningTemplateId !== only.id) {
      setPlanningTemplateId(only.id);
    }
  }, [planningModalOpen, templatesForType, planningTemplateId]);

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: annualReviewsEmployeeQueryKey(employeeId),
    });
    void queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
    void queryClient.invalidateQueries({ queryKey: ["annual-reviews", "planning-suggestions"] });
  };

  const createMutation = useMutation({
    mutationFn: () => {
      const year = planningDate
        ? new Date(planningDate).getFullYear()
        : new Date().getFullYear();
      return createAnnualReview({
        employee_id: employeeId,
        year,
        planned_date: planningDate || null,
        interview_type: planningInterviewType,
        template_id: planningTemplateId || null,
        rh_preparation_template: planningRhNotes || null,
      });
    },
    onSuccess: () => {
      toast({ title: "Entretien planifié" });
      setPlanningModalOpen(false);
      setPlanningDate("");
      setPlanningInterviewType("annual_performance");
      setPlanningTemplateId("");
      setPlanningRhNotes("");
      invalidate();
      void onEmployeeRefresh?.();
    },
    onError: (err: unknown) => {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur",
        description: typeof msg === "string" ? msg : "Planification impossible.",
        variant: "destructive",
      });
    },
  });

  const openPlanning = () => {
    setPlanningDate("");
    setPlanningInterviewType("annual_performance");
    setPlanningTemplateId("");
    setPlanningRhNotes("");
    setPlanningModalOpen(true);
  };

  const handleViewPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      openBlobInNewTab(blob, 100);
    } catch {
      toast({ title: "Erreur", description: "PDF inaccessible.", variant: "destructive" });
    }
  };

  const handleDownloadPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      downloadAnnualReviewPdfFile(blob, reviewId);
      document.body.removeChild(a);
      toast({ title: "PDF téléchargé" });
    } catch {
      toast({ title: "Erreur", description: "Téléchargement impossible.", variant: "destructive" });
    }
  };

  const handleDelete = async (reviewId: string) => {
    setDeletingReviewId(reviewId);
    try {
      await deleteAnnualReview(reviewId);
      toast({ title: "Entretien supprimé" });
      invalidate();
      void onEmployeeRefresh?.();
    } catch (err: unknown) {
      const msg =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail
          : undefined;
      toast({
        title: "Erreur",
        description: typeof msg === "string" ? msg : "Suppression impossible.",
        variant: "destructive",
      });
    } finally {
      setDeletingReviewId(null);
    }
  };

  const renderPdfActions = (review: AnnualReview) => {
    if (review.status !== "cloture") return null;
    return (
      <div className="flex items-center gap-0.5 shrink-0" onClick={(e) => e.stopPropagation()}>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => handleViewPdf(review.id, e)}
          className="h-8 w-8 p-0"
          title="Voir PDF"
        >
          <Eye className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="sm"
          onClick={(e) => handleDownloadPdf(review.id, e)}
          className="h-8 w-8 p-0"
          title="Télécharger PDF"
        >
          <FileDown className="h-4 w-4" />
        </Button>
      </div>
    );
  };

  const renderActionableRow = (r: AnnualReview) => {
    const overdue = isAnnualReviewOverdue(r);
    return (
      <li
        key={r.id}
        className={cn(
          "flex flex-wrap items-center gap-2 sm:gap-3 px-3 py-2.5",
          "hover:bg-muted/40 transition-colors",
          overdue && "bg-destructive/5",
        )}
      >
        <button
          type="button"
          className="flex-1 min-w-[140px] text-left"
          onClick={() => navigate(reviewDetailPath(r.id, employeeId))}
        >
          <span
            className="font-medium text-sm block truncate"
            title={interviewTypeLabel(r.interview_type)}
          >
            {interviewTypeShortLabel(r.interview_type)}
          </span>
          <span className="text-xs text-muted-foreground tabular-nums">
            {r.year}
            {r.planned_date ? ` · ${formatAnnualReviewDate(r.planned_date)}` : ""}
          </span>
          <ReviewExtraMeta review={r} />
        </button>
        <div className="flex flex-col items-end gap-1 shrink-0">
          {overdue && (
            <Badge variant="destructive" className="text-[10px] h-5">
              En retard
            </Badge>
          )}
          <AnnualReviewBadge status={r.status} compact />
        </div>
        <div className="flex items-center gap-1 ml-auto shrink-0">
          <Button
            type="button"
            size="sm"
            className="h-8"
            onClick={() => navigate(reviewDetailPath(r.id, employeeId))}
          >
            Ouvrir
          </Button>
          <ReviewDeleteButton
            review={r}
            canDelete={canDeleteReview}
            deleting={deletingReviewId === r.id}
            onDelete={handleDelete}
          />
        </div>
      </li>
    );
  };

  const renderNextReviewCard = () => {
    if (!nextReview) return null;
    const overdue = isAnnualReviewOverdue(nextReview);
    const showAsPriority = isActionableAnnualReviewStatus(nextReview.status);

    return (
      <div>
        <h4 className="text-sm font-medium mb-2">
          {showAsPriority ? "Prochain entretien à traiter" : "Entretien en cours"}
        </h4>
        <div
          className={cn(
            "rounded-lg border p-4 space-y-3",
            overdue && "border-destructive/50 bg-destructive/5",
          )}
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="space-y-1 min-w-0">
              <p className="font-medium" title={interviewTypeLabel(nextReview.interview_type)}>
                {interviewTypeLabel(nextReview.interview_type)}
              </p>
              <p className="text-sm text-muted-foreground">Année {nextReview.year}</p>
              {nextReview.planned_date && (
                <p className="text-sm text-muted-foreground tabular-nums">
                  Date prévue : {formatAnnualReviewDate(nextReview.planned_date)}
                </p>
              )}
              <ReviewExtraMeta review={nextReview} />
            </div>
            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <AnnualReviewBadge status={nextReview.status} compact />
              {overdue && <Badge variant="destructive">En retard</Badge>}
            </div>
          </div>
          <Button
            type="button"
            size="sm"
            onClick={() => navigate(reviewDetailPath(nextReview.id, employeeId))}
          >
            Ouvrir
          </Button>
        </div>
      </div>
    );
  };

  return (
    <>
      <Card>
        <CardHeader className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-lg">
              <MessageSquare className="h-5 w-5 text-primary" aria-hidden />
              Entretiens
            </CardTitle>
            <CardDescription>
              {employeeName
                ? `Entretiens de ${employeeName}`
                : "Prochain entretien à traiter et historique des cycles"}
            </CardDescription>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="gap-2"
              onClick={() => void reviewsQuery.refetch()}
              disabled={reviewsQuery.isFetching}
            >
              {reviewsQuery.isFetching ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4" />
              )}
              Actualiser
            </Button>
            <Button type="button" variant="outline" size="sm" className="gap-2" asChild>
              <Link to="/annual-reviews">
                <ExternalLink className="h-4 w-4" />
                Pilotage global
              </Link>
            </Button>
            <Button type="button" size="sm" className="gap-1.5" onClick={openPlanning}>
              <Plus className="h-4 w-4" />
              Planifier
            </Button>
          </div>
        </CardHeader>

        <CardContent className="space-y-6 pt-0">
          {reviewsQuery.isLoading ? (
            <TableSkeleton />
          ) : reviewsQuery.isError ? (
            <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm">
              <p className="font-medium text-destructive">Impossible de charger les entretiens</p>
              <p className="text-muted-foreground mt-1">
                Vérifiez vos droits RH ou réessayez. Si le problème persiste, contactez le support.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => void reviewsQuery.refetch()}
              >
                Réessayer
              </Button>
            </div>
          ) : reviews.length === 0 ? (
            <div className="rounded-lg border border-dashed py-8 text-center text-sm text-muted-foreground">
              <p>Aucun entretien</p>
              <Button type="button" size="sm" className="mt-3 gap-1.5" onClick={openPlanning}>
                <Plus className="h-4 w-4" />
                Planifier
              </Button>
            </div>
          ) : (
            <>
              <div className="flex flex-wrap gap-2 text-sm">
                {overdueCount > 0 && (
                  <Badge variant="destructive">
                    {overdueCount} en retard
                  </Badge>
                )}
                {statusCounts.actionable > 0 && (
                  <Badge variant="outline">
                    {statusCounts.actionable} à traiter
                  </Badge>
                )}
                {statusCounts.cloture > 0 && (
                  <Badge variant="secondary">
                    {statusCounts.cloture} clôturé{statusCounts.cloture > 1 ? "s" : ""}
                  </Badge>
                )}
              </div>

              {renderNextReviewCard()}

              {otherActionableReviews.length > 0 && (
                <section aria-label="Autres entretiens à traiter">
                  <div className="flex items-center gap-2 mb-2">
                    <h3 className="text-sm font-semibold">À faire</h3>
                    <Badge variant="outline" className="text-xs font-normal">
                      {otherActionableReviews.length}
                    </Badge>
                  </div>
                  <ul className="rounded-lg border divide-y">
                    {otherActionableReviews.map(renderActionableRow)}
                  </ul>
                </section>
              )}

              <section aria-label="Historique des entretiens">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <h3 className="text-sm font-semibold text-muted-foreground">Historique</h3>
                  <div className="flex flex-wrap items-center gap-2 ml-auto">
                    <Select
                      value={filterYear === "all" ? "all" : String(filterYear)}
                      onValueChange={(v) => setFilterYear(v === "all" ? "all" : Number(v))}
                    >
                      <SelectTrigger className="h-8 w-[100px] text-xs">
                        <SelectValue placeholder="Année" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">Toutes</SelectItem>
                        {yearOptions.map((y) => (
                          <SelectItem key={y} value={String(y)}>
                            {y}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Select
                      value={filterStatus}
                      onValueChange={(v) => setFilterStatus(v as AnnualReviewStatus | "all")}
                    >
                      <SelectTrigger className="h-8 w-[130px] text-xs">
                        <SelectValue placeholder="Statut" />
                      </SelectTrigger>
                      <SelectContent>
                        {STATUS_FILTER_OPTIONS.map((opt) => (
                          <SelectItem key={opt.value} value={opt.value}>
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <label className="flex items-center gap-1.5 text-xs text-muted-foreground cursor-pointer">
                      <Checkbox
                        checked={hideClosed}
                        onCheckedChange={(c) => setHideClosed(c === true)}
                      />
                      Sans clôturés
                    </label>
                  </div>
                </div>

                {historicalReviews.length === 0 ? (
                  <p className="text-xs text-muted-foreground py-2">Aucun autre entretien.</p>
                ) : (
                  <div className="space-y-4">
                    {historicalGrouped.sections.map((section) => (
                      <div key={section.year || "flat"}>
                        {historicalGrouped.grouped && (
                          <h4 className="text-xs font-semibold text-muted-foreground mb-2">
                            {section.year}
                          </h4>
                        )}
                        <div className="overflow-x-auto rounded-lg border">
                          <Table>
                            <TableHeader>
                              <TableRow className="hover:bg-transparent">
                                <TableHead className="h-9 text-xs">Type</TableHead>
                                <TableHead className="h-9 text-xs w-16">Année</TableHead>
                                <TableHead className="h-9 text-xs">Date</TableHead>
                                <TableHead className="h-9 text-xs">Statut</TableHead>
                                <TableHead className="h-9 w-20" />
                              </TableRow>
                            </TableHeader>
                            <TableBody>
                              {section.items.map((r) => (
                                <HistoricalReviewRow
                                  key={r.id}
                                  review={r}
                                  employeeId={employeeId}
                                  canDeleteReview={canDeleteReview}
                                  deletingReviewId={deletingReviewId}
                                  onNavigate={navigate}
                                  onDelete={handleDelete}
                                  renderPdfActions={renderPdfActions}
                                />
                              ))}
                            </TableBody>
                          </Table>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </CardContent>
      </Card>

      <Dialog open={planningModalOpen} onOpenChange={setPlanningModalOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Planifier un entretien</DialogTitle>
            <DialogDescription>
              Vous pouvez planifier plusieurs entretiens pour ce collaborateur (types et années
              distincts).
            </DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            {duplicateTypeYearReview && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-amber-100">
                Un entretien « {interviewTypeLabel(planningInterviewType)} » existe déjà pour{" "}
                {planningTargetYear} ({duplicateTypeYearReview.status}). Vous pouvez tout de même en
                créer un autre si nécessaire.
              </div>
            )}
            <div className="grid gap-1.5">
              <Label htmlFor="employee-interview-type" className="text-xs">
                Type *
              </Label>
              <Select
                value={planningInterviewType}
                onValueChange={(v) => {
                  setPlanningInterviewType(v as InterviewType);
                  setPlanningTemplateId("");
                }}
              >
                <SelectTrigger id="employee-interview-type" className="h-9">
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

            <div className="grid gap-1.5">
              <Label htmlFor="employee-template-select" className="text-xs">
                Modèle
              </Label>
              <Select
                value={planningTemplateId || "_none"}
                onValueChange={(v) => setPlanningTemplateId(v === "_none" ? "" : v)}
              >
                <SelectTrigger id="employee-template-select" className="h-9">
                  <SelectValue placeholder="Aucun" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">Aucun</SelectItem>
                  {templatesForType.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="employee-planned-date" className="text-xs">
                Date prévue
              </Label>
              <Input
                id="employee-planned-date"
                type="date"
                className="h-9"
                value={planningDate}
                onChange={(e) => setPlanningDate(e.target.value)}
              />
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="employee-preparation-notes" className="text-xs">
                Notes RH (optionnel)
              </Label>
              <Textarea
                id="employee-preparation-notes"
                placeholder="Points à aborder…"
                value={planningRhNotes}
                onChange={(e) => setPlanningRhNotes(e.target.value)}
                rows={3}
                className="resize-none min-h-[72px] text-sm"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanningModalOpen(false)}>
              Annuler
            </Button>
            <Button onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>
              {createMutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Planifier
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
