import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AnimatePresence, motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import {
  ArrowRight,
  CheckCircle2,
  GraduationCap,
  Mail,
  MessageSquare,
  Sparkles,
  Stethoscope,
} from "lucide-react";

import { getMyAnnualReviews, INTERVIEW_TYPE_LABELS, type AnnualReview, type AnnualReviewStatus } from "@/api/annualReviews";
import { getMedicalSettings, getMyObligations, type ObligationListItem } from "@/api/medicalFollowUp";
import { getPendingSignaturesME, type PendingSignatureItem } from "@/api/signatures";
import { getEnrollments, type TrainingEnrollment } from "@/api/training";
import { useCurrentEmployee } from "@/hooks/useCurrentEmployee";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

const STORAGE_KEY = "eywai-employee-priority-focus-dismissed-v1";

export type PriorityCategory = "signature" | "entretien" | "visite_medicale" | "formation";

export type PriorityUrgency = "high" | "medium" | "low";

export type EmployeePriorityTask = {
  id: string;
  category: PriorityCategory;
  title: string;
  subtitle?: string;
  href: string;
  externalUrl?: string;
  urgency: PriorityUrgency;
};

const CATEGORY_LABEL: Record<PriorityCategory, string> = {
  signature: "Signature",
  entretien: "Entretien",
  visite_medicale: "Visite médicale",
  formation: "Formation",
};

const CATEGORY_ICON: Record<PriorityCategory, typeof Mail> = {
  signature: Mail,
  entretien: MessageSquare,
  visite_medicale: Stethoscope,
  formation: GraduationCap,
};

const VISIT_TYPE_LABELS: Record<string, string> = {
  aptitude_sir_avant_affectation: "Aptitude SIR avant affectation",
  vip_avant_affectation_mineur_nuit: "VIP avant affectation (mineur/nuit)",
  reprise: "Reprise",
  vip: "VIP",
  sir: "SIR",
  mi_carriere_45: "Mi-carrière (45 ans)",
  demande: "À la demande",
};

const URGENCY_RANK: Record<PriorityUrgency, number> = { high: 0, medium: 1, low: 2 };
const CATEGORY_RANK: Record<PriorityCategory, number> = {
  signature: 0,
  entretien: 1,
  visite_medicale: 2,
  formation: 3,
};

function isActionableReviewStatus(status: AnnualReviewStatus): boolean {
  return status === "planifie" || status === "en_attente_acceptation" || status === "accepte";
}

function signatureUrgency(item: PendingSignatureItem): PriorityUrgency {
  const d = item.days_until_expiry;
  if (d != null && d < 3) return "high";
  if (d != null && d <= 7) return "medium";
  if (item.is_urgent) return "medium";
  return "low";
}

function formatShortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("fr-FR", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return "";
  }
}

function daysUntil(iso: string): number | null {
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return null;
  const now = new Date();
  now.setHours(0, 0, 0, 0);
  const d = new Date(t);
  d.setHours(0, 0, 0, 0);
  return Math.ceil((d.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
}

function reviewUrgency(review: AnnualReview): PriorityUrgency {
  if (review.status === "en_attente_acceptation") return "high";
  if (review.planned_date) {
    const days = daysUntil(review.planned_date);
    if (days != null && days <= 7) return "high";
    if (days != null && days <= 21) return "medium";
  }
  return "low";
}

function medicalUrgency(o: ObligationListItem): PriorityUrgency {
  const due = o.due_date ? daysUntil(o.due_date) : null;
  if (due != null && due < 0) return "high";
  if (due != null && due <= 14) return "high";
  if (due != null && due <= 30) return "medium";
  return "low";
}

function enrollmentUrgency(e: TrainingEnrollment): PriorityUrgency {
  if (!e.planned_date) return "low";
  const days = daysUntil(e.planned_date);
  if (days != null && days <= 7) return "high";
  if (days != null && days <= 21) return "medium";
  return "low";
}

function buildTasksFromSources(params: {
  signatures: PendingSignatureItem[];
  reviews: AnnualReview[];
  obligations: ObligationListItem[];
  enrollments: TrainingEnrollment[];
  medicalEnabled: boolean;
}): EmployeePriorityTask[] {
  const out: EmployeePriorityTask[] = [];

  for (const item of params.signatures) {
    const d = item.days_until_expiry;
    let subtitle = "Document à signer";
    if (d != null && d >= 0) subtitle = `Expire dans ${d} jour${d > 1 ? "s" : ""}`;
    else if (d != null && d < 0) subtitle = "Échéance dépassée";
    out.push({
      id: `signature:${item.id}`,
      category: "signature",
      title: item.document_name?.trim() || "Document à signer",
      subtitle,
      href: "/employee/documents",
      externalUrl: item.yousign_procedure_id
        ? `https://app.yousign.com/procedure/${item.yousign_procedure_id}`
        : undefined,
      urgency: signatureUrgency(item),
    });
  }

  for (const review of params.reviews) {
    if (!isActionableReviewStatus(review.status)) continue;
    const typeKey = (review.interview_type as string) || "annual_performance";
    const typeLabel = INTERVIEW_TYPE_LABELS[typeKey as keyof typeof INTERVIEW_TYPE_LABELS] || "Entretien";
    const dateLabel = review.planned_date ? ` · ${formatShortDate(review.planned_date)}` : "";
    out.push({
      id: `entretien:${review.id}`,
      category: "entretien",
      title: typeLabel,
      subtitle: `Statut : ${review.status.replace(/_/g, " ")}${dateLabel}`,
      href: `/annual-reviews/${review.id}`,
      urgency: reviewUrgency(review),
    });
  }

  if (params.medicalEnabled) {
    for (const o of params.obligations) {
      if (o.status === "realisee" || o.status === "annulee") continue;
      const label = VISIT_TYPE_LABELS[o.visit_type] || o.visit_type;
      out.push({
        id: `visite:${o.id}`,
        category: "visite_medicale",
        title: label,
        subtitle: o.due_date ? `Échéance : ${formatShortDate(o.due_date)}` : "Visite à planifier ou réaliser",
        href: "/medical-follow-up",
        urgency: medicalUrgency(o),
      });
    }
  }

  for (const e of params.enrollments) {
    const s = (e.status || "").toLowerCase();
    if (s === "completed" || s === "cancelled") continue;
    out.push({
      id: `formation:${e.id}`,
      category: "formation",
      title: e.training_title?.trim() || "Formation",
      subtitle: e.planned_date ? `Prévue le ${formatShortDate(e.planned_date)}` : "Action formation en cours",
      href: "/employee/formation",
      urgency: enrollmentUrgency(e),
    });
  }

  out.sort((a, b) => {
    const du = URGENCY_RANK[a.urgency] - URGENCY_RANK[b.urgency];
    if (du !== 0) return du;
    return CATEGORY_RANK[a.category] - CATEGORY_RANK[b.category];
  });

  return out;
}

function urgencyCardClass(u: PriorityUrgency): string {
  switch (u) {
    case "high":
      return "border-l-[3px] border-l-red-500/90 border-y border-r border-border/70 bg-card shadow-sm";
    case "medium":
      return "border-l-[3px] border-l-amber-500/85 border-y border-r border-border/70 bg-card shadow-sm";
    default:
      return "border-l-[3px] border-l-sky-500/80 border-y border-r border-border/70 bg-card shadow-sm";
  }
}

function loadDismissed(): Set<string> {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as unknown;
    if (!Array.isArray(arr)) return new Set();
    return new Set(arr.filter((x): x is string => typeof x === "string"));
  } catch {
    return new Set();
  }
}

export function EmployeePriorityFocus() {
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState<Set<string>>(loadDismissed);
  const [currentIndex, setCurrentIndex] = useState(0);

  useEffect(() => {
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify([...dismissed]));
    } catch {
      /* ignore */
    }
  }, [dismissed]);

  const signaturesQuery = useQuery({
    queryKey: ["pending-signatures", "employee-priority-focus"],
    queryFn: getPendingSignaturesME,
  });

  const reviewsQuery = useQuery({
    queryKey: ["annual-reviews-me", "employee-priority-focus"],
    queryFn: async () => (await getMyAnnualReviews()).data ?? [],
  });

  const medicalSettingsQuery = useQuery({
    queryKey: ["medical-follow-up", "settings", "employee-priority-focus"],
    queryFn: getMedicalSettings,
  });

  const obligationsQuery = useQuery({
    queryKey: ["medical-follow-up", "me", "employee-priority-focus"],
    queryFn: getMyObligations,
    enabled: medicalSettingsQuery.data?.enabled === true,
  });

  const { employee, isLoading: employeeLoading } = useCurrentEmployee();

  const enrollmentsQuery = useQuery({
    queryKey: ["training-enrollments", "employee-priority-focus", employee?.id],
    queryFn: async () => getEnrollments({ employee_id: employee!.id }),
    enabled: Boolean(employee?.id),
  });

  const allTasks = useMemo(() => {
    return buildTasksFromSources({
      signatures: signaturesQuery.data?.items ?? [],
      reviews: reviewsQuery.data ?? [],
      obligations: obligationsQuery.data ?? [],
      enrollments: enrollmentsQuery.data ?? [],
      medicalEnabled: medicalSettingsQuery.data?.enabled === true,
    });
  }, [
    signaturesQuery.data,
    reviewsQuery.data,
    obligationsQuery.data,
    enrollmentsQuery.data,
    medicalSettingsQuery.data?.enabled,
  ]);

  const activeList = useMemo(
    () => allTasks.filter((t) => !dismissed.has(t.id)),
    [allTasks, dismissed],
  );

  useEffect(() => {
    setCurrentIndex((i) => {
      if (activeList.length === 0) return 0;
      return Math.min(i, activeList.length - 1);
    });
  }, [activeList.length]);

  const showLoading =
    signaturesQuery.isPending ||
    reviewsQuery.isPending ||
    medicalSettingsQuery.isPending ||
    (medicalSettingsQuery.data?.enabled === true && obligationsQuery.isPending) ||
    employeeLoading ||
    (Boolean(employee?.id) && enrollmentsQuery.isPending);

  const currentTask = activeList[currentIndex] ?? null;

  const openModule = useCallback(
    (task: EmployeePriorityTask) => {
      if (task.externalUrl) {
        window.open(task.externalUrl, "_blank", "noopener,noreferrer");
        return;
      }
      navigate(task.href);
    },
    [navigate],
  );

  const handleNext = useCallback(() => {
    setCurrentIndex((i) => {
      const n = activeList.length;
      if (n <= 1) return 0;
      return (i + 1) % n;
    });
  }, [activeList.length]);

  const handleDismiss = useCallback(() => {
    if (!currentTask) return;
    setDismissed((prev) => new Set([...prev, currentTask.id]));
  }, [currentTask]);

  const CatIcon = currentTask ? CATEGORY_ICON[currentTask.category] : Sparkles;

  return (
    <Card className={cn("w-full overflow-hidden", currentTask && urgencyCardClass(currentTask.urgency))}>
      <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0 pb-2">
        <div className="flex min-w-0 flex-1 items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">
            <CatIcon className="h-5 w-5" aria-hidden />
          </div>
          <div className="min-w-0 space-y-1">
            <CardTitle className="text-base font-semibold leading-tight">Focus priorité</CardTitle>
            <CardDescription className="text-xs sm:text-sm">
              Une action à la fois : signatures, entretiens, suivi médical, formations.
            </CardDescription>
          </div>
        </div>
        {activeList.length > 0 && !showLoading && (
          <Badge variant="secondary" className="shrink-0 tabular-nums">
            {currentIndex + 1} / {activeList.length}
          </Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {showLoading && (
          <div className="space-y-3" aria-busy="true">
            <Skeleton className="h-5 w-2/3 max-w-md" />
            <Skeleton className="h-4 w-full max-w-lg" />
            <div className="flex flex-wrap gap-2 pt-2">
              <Skeleton className="h-9 w-36" />
              <Skeleton className="h-9 w-24" />
              <Skeleton className="h-9 w-44" />
            </div>
          </div>
        )}

        {!showLoading && activeList.length === 0 && (
          <div className="flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-emerald-500/35 bg-emerald-500/[0.06] py-10 text-center">
            <CheckCircle2 className="h-12 w-12 text-emerald-600 dark:text-emerald-400" aria-hidden />
            <p className="max-w-md text-sm font-medium text-foreground">
              Bravo, vous n&apos;avez plus de tâches prioritaires
            </p>
            <p className="text-xs text-muted-foreground">
              Nous vous préviendrons lorsque de nouvelles actions seront nécessaires.
            </p>
          </div>
        )}

        {!showLoading && currentTask && (
          <div className="space-y-4">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={currentTask.id}
                initial={{ opacity: 0, x: 14 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -12 }}
                transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                className="space-y-2"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant="outline" className="text-[10px] font-semibold uppercase tracking-wide">
                    {CATEGORY_LABEL[currentTask.category]}
                  </Badge>
                  {currentTask.urgency === "high" && (
                    <Badge className="bg-red-600 text-white hover:bg-red-600">Urgent</Badge>
                  )}
                </div>
                <p className="text-lg font-semibold leading-snug text-foreground">{currentTask.title}</p>
                {currentTask.subtitle && (
                  <p className="text-sm text-muted-foreground">{currentTask.subtitle}</p>
                )}
              </motion.div>
            </AnimatePresence>

            <div className="flex flex-wrap items-center gap-2 border-t border-border/60 pt-4">
              <Button type="button" className="gap-2" onClick={() => openModule(currentTask)}>
                <ArrowRight className="h-4 w-4 shrink-0" aria-hidden />
                Ouvrir le module
              </Button>
              <Button
                type="button"
                variant="secondary"
                onClick={handleNext}
                disabled={activeList.length <= 1}
              >
                Suivant
              </Button>
              <Button type="button" variant="outline" onClick={handleDismiss}>
                Marquer comme terminé
              </Button>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
