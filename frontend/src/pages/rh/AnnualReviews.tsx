// src/pages/AnnualReviews.tsx
// Page RH : liste et suivi des entretiens

import { RhPageHeader } from '@/components/layout';
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { useCompany } from "@/contexts/CompanyContext";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import apiClient from "@/api/apiClient";
import {
  getAllAnnualReviews,
  getEmployeeAnnualReviews,
  createAnnualReview,
  deleteAnnualReview,
  downloadAnnualReviewPdf,
  countUpcomingPlannedAnnualReviews,
  ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS,
  INTERVIEW_TYPE_LABELS,
  type InterviewType,
} from "@/api/annualReviews";
import type {
  AnnualReviewListItem,
  AnnualReviewStatus,
} from "@/api/annualReviews";
import { getTemplates } from "@/api/interviewTemplates";
import {
  canRhDeleteAnnualReview,
  countListItemsByStatus,
  countOverdueActionableReviews,
  findExistingReviewSameTypeYear,
  getListItemDateDisplay,
  interviewTypeShortLabel,
  isAnnualReviewOverdue,
  listItemExtraMetaLines,
  sortListItemsForDisplay,
} from "@/lib/annualReviewLabels";
import { cn } from "@/lib/utils";
import {
  Loader2,
  Search,
  MessageSquare,
  Plus,
  ChevronRight,
  Trash2,
  FileDown,
  Eye,
  AlertTriangle,
  RefreshCw,
} from "lucide-react";
import { downloadAnnualReviewPdfFile, previewAnnualReviewPdf } from '@/lib/annualReviewPdf';
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

const STATUS_FILTER_OPTIONS: { value: AnnualReviewStatus | "all"; label: string }[] = [
  { value: "all", label: "Tous" },
  { value: "planifie", label: "Planifié" },
  { value: "en_attente_acceptation", label: "En attente d'acceptation" },
  { value: "accepte", label: "Accepté" },
  { value: "refuse", label: "Refusé" },
  { value: "realise", label: "Réalisé" },
  { value: "cloture", label: "Clôturé" },
];

const QUICK_STATUS_GROUPS: {
  id: string;
  label: string;
  statuses: AnnualReviewStatus[] | null;
}[] = [
  { id: "all", label: "Tous", statuses: null },
  {
    id: "a_traiter",
    label: "À traiter",
    statuses: ["planifie", "en_attente_acceptation", "accepte"],
  },
  { id: "refuses", label: "Refusés", statuses: ["refuse"] },
  { id: "clotures", label: "Clôturés", statuses: ["realise", "cloture"] },
];

function TableSkeleton() {
  return (
    <div className="space-y-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <Skeleton key={i} className="h-12 w-full" />
      ))}
    </div>
  );
}

function employeeEntretiensHref(employeeId: string) {
  return `/employees/${employeeId}?tab=entretiens`;
}

function isUpcomingInPriorityWindow(item: AnnualReviewListItem): boolean {
  if (!item.planned_date) return false;
  if (
    item.status !== "planifie" &&
    item.status !== "en_attente_acceptation" &&
    item.status !== "accepte"
  ) {
    return false;
  }
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const maxDate = new Date(now);
  maxDate.setDate(maxDate.getDate() + ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS);
  const planned = new Date(
    item.planned_date.includes("T") ? item.planned_date : `${item.planned_date}T12:00:00`,
  );
  planned.setHours(0, 0, 0, 0);
  return planned >= now && planned <= maxDate;
}

export type AnnualReviewsProps = {
  /** Intégré dans Formation & talents : masque le titre page. */
  embedded?: boolean;
  /** Navigation retour depuis le détail vers le hub Formation. */
  fromFormationHub?: boolean;
  /** Ouvre l’onglet Paramètres > trames d’entretien. */
  onManageTemplates?: () => void;
};

export default function AnnualReviews({
  embedded = false,
  fromFormationHub = false,
  onManageTemplates,
}: AnnualReviewsProps = {}) {
  const { toast } = useToast();
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { activeCompany } = useCompany();
  const activeCompanyId = activeCompany?.company_id ?? "";

  const openReviewDetail = (reviewId: string) => {
    navigate(
      `/annual-reviews/${reviewId}`,
      fromFormationHub ? { state: { fromFormationHub: true } } : undefined,
    );
  };

  const currentYear = new Date().getFullYear();
  const yearOptions = Array.from({ length: 6 }, (_, i) => currentYear - i);
  const focusUpcoming = searchParams.get("focus") === "upcoming";
  const focusSignaturePending =
    (searchParams.get("signature_status") ?? "").toLowerCase() === "pending";

  const [filterYear, setFilterYear] = useState<number | "all">(currentYear);
  const [filterStatus, setFilterStatus] = useState<AnnualReviewStatus | "all">("all");
  const [filterInterviewType, setFilterInterviewType] = useState<InterviewType | "all">("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [hideClosed, setHideClosed] = useState(true);
  const [planningModalOpen, setPlanningModalOpen] = useState(false);
  const [planningEmployeeId, setPlanningEmployeeId] = useState("");
  const [planningDate, setPlanningDate] = useState("");
  const [quickGroup, setQuickGroup] = useState<string>(focusUpcoming ? "a_traiter" : "all");
  const [planningInterviewType, setPlanningInterviewType] =
    useState<InterviewType>("annual_performance");
  const [planningTemplateId, setPlanningTemplateId] = useState("");
  const [planningRhNotes, setPlanningRhNotes] = useState("");

  const {
    data: list = [],
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: [
      "annual-reviews",
      filterYear === "all" ? null : filterYear,
      filterStatus === "all" ? null : filterStatus,
      activeCompanyId,
    ],
    queryFn: async () => {
      const res = await getAllAnnualReviews({
        year: filterYear === "all" ? undefined : filterYear,
        status: filterStatus === "all" ? undefined : filterStatus,
      });
      return res.data;
    },
    enabled: !!activeCompanyId,
  });

  const statusCounts = useMemo(() => countListItemsByStatus(list), [list]);
  const overdueCount = useMemo(() => countOverdueActionableReviews(list), [list]);
  const upcomingCount = useMemo(
    () => countUpcomingPlannedAnnualReviews(list),
    [list],
  );

  const { data: employees = [] } = useQuery({
    queryKey: ["employees", activeCompanyId],
    queryFn: async () => {
      const res = await apiClient.get("/api/employees");
      return res.data;
    },
    enabled: !!activeCompanyId && planningModalOpen,
  });

  const { data: planningEmployeeReviews = [] } = useQuery({
    queryKey: ["annual-reviews", "employee", planningEmployeeId, "planning"],
    queryFn: async () => {
      const res = await getEmployeeAnnualReviews(planningEmployeeId);
      return res.data ?? [];
    },
    enabled: !!planningEmployeeId && planningModalOpen,
  });

  const { data: interviewTemplates = [] } = useQuery({
    queryKey: ["interview-templates", activeCompanyId],
    queryFn: async () => {
      const res = await getTemplates();
      return res.data;
    },
    enabled: !!activeCompanyId && planningModalOpen,
  });

  const templatesForType = useMemo(
    () =>
      interviewTemplates.filter(
        (t) => t.status === "active" && t.interview_type === planningInterviewType,
      ),
    [interviewTemplates, planningInterviewType],
  );

  const planningTargetYear = useMemo(() => {
    if (planningDate) return new Date(planningDate).getFullYear();
    return currentYear;
  }, [planningDate, currentYear]);

  const duplicateTypeYearReview = useMemo(
    () =>
      findExistingReviewSameTypeYear(
        planningEmployeeReviews,
        planningInterviewType,
        planningTargetYear,
      ),
    [planningEmployeeReviews, planningInterviewType, planningTargetYear],
  );

  const createMutation = useMutation({
    mutationFn: createAnnualReview,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
      setPlanningModalOpen(false);
      setPlanningEmployeeId("");
      setPlanningDate("");
      setPlanningInterviewType("annual_performance");
      setPlanningTemplateId("");
      setPlanningRhNotes("");
      toast({
        title: "Entretien planifié",
        description:
          "L'entretien est créé au statut « Planifié ». Le collaborateur pourra l'accepter depuis son espace.",
      });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de planifier l'entretien.",
        variant: "destructive",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: deleteAnnualReview,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["annual-reviews"] });
      toast({ title: "Entretien supprimé", description: "L'entretien a été supprimé avec succès." });
    },
    onError: (err: Error) => {
      toast({
        title: "Erreur",
        description: err?.message ?? "Impossible de supprimer l'entretien.",
        variant: "destructive",
      });
    },
  });

  useEffect(() => {
    if (isError) {
      toast({
        title: "Erreur",
        description:
          (error as Error)?.message ?? "Impossible de charger les entretiens.",
        variant: "destructive",
      });
    }
  }, [isError, error, toast]);

  const activeFiltersSummary = useMemo(() => {
    const parts: string[] = [];
    if (filterYear !== "all") parts.push(`année ${filterYear}`);
    if (filterStatus !== "all") {
      const opt = STATUS_FILTER_OPTIONS.find((o) => o.value === filterStatus);
      parts.push(opt?.label ?? filterStatus);
    }
    const pill = QUICK_STATUS_GROUPS.find((g) => g.id === quickGroup);
    if (quickGroup !== "all" && pill) parts.push(`vue « ${pill.label} »`);
    if (filterInterviewType !== "all") {
      parts.push(INTERVIEW_TYPE_LABELS[filterInterviewType]);
    }
    if (hideClosed) parts.push("clôturés masqués");
    if (focusUpcoming) parts.push(`échéance sous ${ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS} jours`);
    if (focusSignaturePending) parts.push("signatures en attente");
    if (searchTerm.trim()) parts.push(`recherche « ${searchTerm.trim()} »`);
    return parts;
  }, [
    filterYear,
    filterStatus,
    quickGroup,
    filterInterviewType,
    hideClosed,
    focusUpcoming,
    focusSignaturePending,
    searchTerm,
  ]);

  const filteredList = useMemo(() => {
    let items: AnnualReviewListItem[] = list;

    // Masquer les clôturés sauf vue « signatures en attente » (souvent statut clôture + pending)
    if (hideClosed && !focusSignaturePending) {
      items = items.filter((item) => item.status !== "cloture");
    }

    const group = QUICK_STATUS_GROUPS.find((g) => g.id === quickGroup);
    if (group?.statuses) {
      items = items.filter((item) =>
        group.statuses!.includes(item.status as AnnualReviewStatus),
      );
    }

    if (filterInterviewType !== "all") {
      items = items.filter(
        (item) => (item.interview_type ?? "annual_performance") === filterInterviewType,
      );
    }

    if (focusUpcoming) {
      items = items.filter(isUpcomingInPriorityWindow);
    }

    if (focusSignaturePending) {
      items = items.filter(
        (item) => (item.signature_status ?? "").toLowerCase() === "pending",
      );
    }

    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase();
      items = items.filter(
        (item) =>
          item.first_name.toLowerCase().includes(term) ||
          item.last_name.toLowerCase().includes(term),
      );
    }

    return sortListItemsForDisplay(items);
  }, [
    list,
    searchTerm,
    quickGroup,
    hideClosed,
    filterInterviewType,
    focusUpcoming,
    focusSignaturePending,
  ]);

  const isEmpty = list.length === 0;
  const noResults = !isEmpty && filteredList.length === 0;

  const handleQuickGroup = (id: string) => {
    setQuickGroup(id);
    if (id !== "all") setFilterStatus("all");
    if (focusUpcoming) {
      const next = new URLSearchParams(searchParams);
      next.delete("focus");
      setSearchParams(next, { replace: true });
    }
  };

  const handleFilterStatusChange = (value: AnnualReviewStatus | "all") => {
    setFilterStatus(value);
    if (value !== "all") setQuickGroup("all");
  };

  const handleShowActionable = () => {
    handleQuickGroup("a_traiter");
    setHideClosed(true);
    if (filterYear === "all") setFilterYear(currentYear);
  };

  const handleOpenPlanning = () => {
    setPlanningEmployeeId("");
    setPlanningDate("");
    setPlanningInterviewType("annual_performance");
    setPlanningTemplateId("");
    setPlanningRhNotes("");
    setPlanningModalOpen(true);
  };

  const handlePlanSubmit = () => {
    if (!planningEmployeeId) {
      toast({
        title: "Champ requis",
        description: "Veuillez sélectionner un employé.",
        variant: "destructive",
      });
      return;
    }
    const year = planningDate
      ? new Date(planningDate).getFullYear()
      : currentYear;

    createMutation.mutate({
      employee_id: planningEmployeeId,
      year,
      planned_date: planningDate ? planningDate : null,
      interview_type: planningInterviewType,
      template_id: planningTemplateId || null,
      rh_preparation_template: planningRhNotes.trim() || null,
    });
  };

  const handleViewPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
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

  const handleDownloadPdf = async (reviewId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const blob = await downloadAnnualReviewPdf(reviewId);
      downloadAnnualReviewPdfFile(blob, reviewId);
      document.body.removeChild(a);
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

  return (
    <div className="space-y-6">
      {!embedded ? (
        <div className="space-y-3">
          <RhPageHeader
            title="Entretiens"
            description={`Suivi des entretiens des collaborateurs${activeCompany?.company_name ? ` — ${activeCompany.company_name}` : ''}.`}
          />
          {!isLoading && !isError && list.length > 0 ? (
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <Badge variant="secondary" className="font-normal">
                {statusCounts.actionable} à traiter
              </Badge>
              {overdueCount > 0 ? (
                <Badge variant="destructive" className="font-normal">
                  {overdueCount} en retard
                </Badge>
              ) : null}
              <Badge variant="outline" className="font-normal">
                {upcomingCount} planifiés sous {ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS} jours
              </Badge>
              <span className="text-muted-foreground text-xs hidden sm:inline">
                (pastille sidebar)
              </span>
              {statusCounts.actionable > 0 ? (
                <Button
                  type="button"
                  variant="link"
                  className="h-auto p-0 text-xs"
                  onClick={handleShowActionable}
                >
                  Voir les entretiens à traiter
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      ) : null}

      <Card>
        <CardHeader className="pb-4 space-y-4">
          <div className="flex flex-wrap gap-2">
            {QUICK_STATUS_GROUPS.map((g) => (
              <Button
                key={g.id}
                type="button"
                size="sm"
                variant={quickGroup === g.id ? "secondary" : "outline"}
                onClick={() => handleQuickGroup(g.id)}
              >
                {g.label}
              </Button>
            ))}
            {focusUpcoming ? (
              <Badge variant="outline" className="self-center">
                Échéance {ANNUAL_REVIEW_PRIORITY_WINDOW_DAYS} j
                <button
                  type="button"
                  className="ml-1 underline text-xs"
                  onClick={() => {
                    const next = new URLSearchParams(searchParams);
                    next.delete("focus");
                    setSearchParams(next, { replace: true });
                  }}
                >
                  retirer
                </button>
              </Badge>
            ) : null}
          </div>

          <div className="flex flex-col gap-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Rechercher par nom ou prénom..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="pl-10"
              />
            </div>
            <div className="flex flex-wrap gap-2 items-center">
              <Select
                value={filterYear === "all" ? "all" : String(filterYear)}
                onValueChange={(v) =>
                  setFilterYear(v === "all" ? "all" : Number(v))
                }
              >
                <SelectTrigger className="w-[140px]">
                  <SelectValue placeholder="Année" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes les années</SelectItem>
                  {yearOptions.map((y) => (
                    <SelectItem key={y} value={String(y)}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={filterStatus}
                onValueChange={(v) =>
                  handleFilterStatusChange(v as AnnualReviewStatus | "all")
                }
                disabled={quickGroup !== "all"}
              >
                <SelectTrigger className="w-[200px]">
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

              <Select
                value={filterInterviewType}
                onValueChange={(v) =>
                  setFilterInterviewType(v as InterviewType | "all")
                }
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Type" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tous les types</SelectItem>
                  {(Object.keys(INTERVIEW_TYPE_LABELS) as InterviewType[]).map((k) => (
                    <SelectItem key={k} value={k}>
                      {INTERVIEW_TYPE_LABELS[k]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <div className="flex items-center gap-2">
                <Checkbox
                  id="hide-closed"
                  checked={hideClosed}
                  onCheckedChange={(c) => setHideClosed(c === true)}
                />
                <Label htmlFor="hide-closed" className="text-sm font-normal cursor-pointer">
                  Masquer les clôturés
                </Label>
              </div>

              {embedded && onManageTemplates ? (
                <Button type="button" variant="outline" onClick={onManageTemplates}>
                  Gérer les trames
                </Button>
              ) : null}
              <Button onClick={handleOpenPlanning} className="ml-auto sm:ml-0">
                <Plus className="mr-2 h-4 w-4" />
                Planifier un entretien
              </Button>
            </div>
          </div>
        </CardHeader>

        <CardContent>
          {isLoading ? (
            <TableSkeleton />
          ) : isError ? (
            <div className="flex flex-col items-center justify-center gap-4 py-12 text-center">
              <div className="text-destructive">
                <p className="font-medium">Erreur de chargement</p>
                <p className="text-sm mt-1 text-muted-foreground">
                  {(error as Error)?.message ?? "Impossible de charger les entretiens."}
                </p>
              </div>
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
          ) : isEmpty ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucun entretien</p>
              <p className="text-sm mt-1 mb-4">
                Planifiez un entretien pour commencer le suivi.
              </p>
              <Button onClick={handleOpenPlanning}>
                <Plus className="mr-2 h-4 w-4" />
                Planifier un entretien
              </Button>
            </div>
          ) : noResults ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
              <Search className="h-12 w-12 mb-4 opacity-50" />
              <p className="font-medium">Aucun résultat</p>
              <p className="text-sm mt-1 max-w-md">
                Modifiez les filtres ou la recherche.
                {activeFiltersSummary.length > 0 ? (
                  <span className="block mt-2 text-xs">
                    Filtres actifs : {activeFiltersSummary.join(" · ")}
                  </span>
                ) : null}
              </p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Collaborateur</TableHead>
                  <TableHead className="hidden md:table-cell">Type</TableHead>
                  <TableHead>Année</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right w-[140px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredList.map((item) => {
                  const overdue = isAnnualReviewOverdue(item);
                  const dateDisplay = getListItemDateDisplay(item);
                  const metaLines = listItemExtraMetaLines(item);
                  const canDelete = canRhDeleteAnnualReview(item.status);

                  return (
                    <TableRow
                      key={item.id}
                      className={cn(
                        "cursor-pointer hover:bg-muted/50 transition-colors",
                        overdue && "bg-destructive/5",
                      )}
                      onClick={() => openReviewDetail(item.id)}
                    >
                      <TableCell>
                        <div className="font-medium">
                          <Link
                            to={employeeEntretiensHref(item.employee_id)}
                            className="hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {item.first_name} {item.last_name}
                          </Link>
                        </div>
                        {item.job_title ? (
                          <p className="text-xs text-muted-foreground mt-0.5 md:hidden">
                            {item.job_title}
                          </p>
                        ) : null}
                      </TableCell>
                      <TableCell
                        className="hidden md:table-cell text-muted-foreground text-sm"
                        title={item.interview_type ?? undefined}
                      >
                        {interviewTypeShortLabel(item.interview_type)}
                      </TableCell>
                      <TableCell className="tabular-nums text-muted-foreground">
                        {item.year}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        <span className="text-xs text-muted-foreground/80 block">
                          {dateDisplay.label}
                        </span>
                        <span className="tabular-nums">{dateDisplay.value}</span>
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-col items-start gap-1">
                          <div className="flex flex-wrap items-center gap-1">
                            {overdue ? (
                              <Badge variant="destructive" className="text-[10px] h-5">
                                En retard
                              </Badge>
                            ) : null}
                            <AnnualReviewBadge
                              status={item.status as AnnualReviewStatus}
                              compact
                            />
                          </div>
                          {metaLines.length > 0 ? (
                            <div className="flex flex-wrap gap-x-2 text-[10px] text-muted-foreground">
                              {metaLines.map((line) => (
                                <span key={line}>{line}</span>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell
                        className="text-right"
                        onClick={(e) => e.stopPropagation()}
                      >
                        <div className="flex items-center justify-end gap-0.5">
                          {item.status === "cloture" ? (
                            <>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => handleViewPdf(item.id, e)}
                                className="h-8 w-8 p-0"
                                title="Voir le PDF"
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={(e) => handleDownloadPdf(item.id, e)}
                                className="h-8 w-8 p-0"
                                title="Télécharger le PDF"
                              >
                                <FileDown className="h-4 w-4" />
                              </Button>
                            </>
                          ) : null}
                          {canDelete ? (
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                                  title="Supprimer"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent>
                                <AlertDialogHeader>
                                  <AlertDialogTitle>Supprimer l&apos;entretien</AlertDialogTitle>
                                  <AlertDialogDescription>
                                    Supprimer l&apos;entretien de {item.first_name}{" "}
                                    {item.last_name} ? Action irréversible.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel>Annuler</AlertDialogCancel>
                                  <AlertDialogAction
                                    onClick={() => deleteMutation.mutate(item.id)}
                                    className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                                    disabled={deleteMutation.isPending}
                                  >
                                    {deleteMutation.isPending ? (
                                      <>
                                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                                        Suppression...
                                      </>
                                    ) : (
                                      "Supprimer"
                                    )}
                                  </AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          ) : null}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="h-8 w-8 p-0"
                            title="Ouvrir"
                            onClick={() => openReviewDetail(item.id)}
                          >
                            <ChevronRight className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <Dialog open={planningModalOpen} onOpenChange={setPlanningModalOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Planifier un entretien</DialogTitle>
          </DialogHeader>
          <div className="grid gap-6 py-4">
            <div className="grid gap-2">
              <Label htmlFor="employee-select">Employé *</Label>
              <Select
                value={planningEmployeeId}
                onValueChange={setPlanningEmployeeId}
              >
                <SelectTrigger id="employee-select">
                  <SelectValue placeholder="Sélectionner un employé" />
                </SelectTrigger>
                <SelectContent>
                  {employees.map((emp: { id: string; first_name: string; last_name: string }) => (
                    <SelectItem key={emp.id} value={emp.id}>
                      {emp.first_name} {emp.last_name}
                    </SelectItem>
                  ))}
                  {employees.length === 0 && (
                    <SelectItem value="_" disabled>
                      Aucun employé disponible
                    </SelectItem>
                  )}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-2">
              <Label htmlFor="interview-type">Type d&apos;entretien *</Label>
              <Select
                value={planningInterviewType}
                onValueChange={(v) => {
                  setPlanningInterviewType(v as InterviewType);
                  setPlanningTemplateId("");
                }}
              >
                <SelectTrigger id="interview-type">
                  <SelectValue placeholder="Choisir un type" />
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

            {duplicateTypeYearReview ? (
              <div className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 dark:bg-amber-950/30 dark:border-amber-900 p-3 text-sm text-amber-900 dark:text-amber-100">
                <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                <p>
                  Un entretien de ce type existe déjà pour {planningTargetYear} (
                  statut : {duplicateTypeYearReview.status}). Vous pouvez tout de même en
                  créer un autre si nécessaire.
                </p>
              </div>
            ) : null}

            <div className="grid gap-2">
              <Label htmlFor="template-select">Modèle de trame (optionnel)</Label>
              <Select
                value={planningTemplateId || "_none"}
                onValueChange={(v) => setPlanningTemplateId(v === "_none" ? "" : v)}
              >
                <SelectTrigger id="template-select">
                  <SelectValue placeholder="Aucun modèle" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="_none">Aucun modèle</SelectItem>
                  {templatesForType.map((t) => (
                    <SelectItem key={t.id} value={t.id}>
                      {t.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {templatesForType.length === 0 && (
                <p className="text-xs text-muted-foreground">
                  Aucun modèle actif pour ce type.
                  {onManageTemplates ? (
                    <>
                      {" "}
                      <button
                        type="button"
                        className="underline text-primary"
                        onClick={onManageTemplates}
                      >
                        Créer une trame
                      </button>
                    </>
                  ) : (
                    " Vous pouvez en créer dans Paramètres > Trames d'entretien."
                  )}
                </p>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="planned-date">Date prévue</Label>
              <Input
                id="planned-date"
                type="date"
                value={planningDate}
                onChange={(e) => setPlanningDate(e.target.value)}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="rh-notes">Notes RH (optionnel)</Label>
              <Textarea
                id="rh-notes"
                value={planningRhNotes}
                onChange={(e) => setPlanningRhNotes(e.target.value)}
                placeholder="Points à aborder, contexte…"
                rows={3}
              />
            </div>

            <p className="text-xs text-muted-foreground">
              L&apos;entretien sera créé au statut « Planifié ». Le collaborateur pourra
              l&apos;accepter depuis son espace.
            </p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPlanningModalOpen(false)}>
              Annuler
            </Button>
            <Button
              onClick={handlePlanSubmit}
              disabled={!planningEmployeeId || createMutation.isPending}
            >
              {createMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : null}
              Planifier l&apos;entretien
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
