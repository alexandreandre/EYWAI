// Page RH unifiée Pack Talent — /formation (+ hash par onglet)

import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import {
  getEvaluationsSummary,
  getPendingManagerApproval,
  getPendingRHApproval,
  managerApprove,
  rhApprove,
  type EvaluationSummary,
  type TrainingEnrollment,
} from "@/api/training";
import { getDashboardCounts } from "@/api/certifications";
import { getOverdueCount } from "@/api/legalObligations";

const LazyAnnualReviews = lazy(() => import("@/pages/AnnualReviews"));
const LazyInterviewTemplatesTab = lazy(() => import("@/pages/formation/tabs/InterviewTemplatesTab"));
const LazyObjectivesTab = lazy(() => import("@/pages/formation/tabs/ObjectivesTab"));
const LazyHabilitationsTab = lazy(() => import("@/pages/formation/tabs/HabilitationsTab"));
const LazyCatalogueTab = lazy(() => import("@/pages/formation/tabs/CatalogueTab"));
const LazyBudgetTab = lazy(() => import("@/pages/formation/tabs/BudgetTab"));
const LazyObligationsLegalesTab = lazy(() => import("@/pages/formation/tabs/ObligationsLegalesTab"));
const LazyCompetencesTab = lazy(() => import("@/pages/formation/tabs/CompetencesTab"));

export type FormationTabId =
  | "entretiens"
  | "trames"
  | "objectifs"
  | "habilitations"
  | "catalogue"
  | "budget"
  | "obligations"
  | "competences"
  | "demandes";

const TAB_IDS: FormationTabId[] = [
  "entretiens",
  "trames",
  "objectifs",
  "habilitations",
  "catalogue",
  "budget",
  "obligations",
  "competences",
  "demandes",
];

const HASH_BY_TAB: Record<FormationTabId, string> = {
  entretiens: "entretiens",
  trames: "trames",
  objectifs: "objectifs",
  habilitations: "habilitations",
  catalogue: "catalogue",
  budget: "budget",
  obligations: "obligations",
  competences: "competences",
  demandes: "demandes",
};

const TAB_BY_HASH: Record<string, FormationTabId> = Object.fromEntries(
  TAB_IDS.map((id) => [HASH_BY_TAB[id], id]),
) as Record<string, FormationTabId>;

function parseHashTab(): FormationTabId {
  const raw = window.location.hash.replace(/^#/, "").trim().toLowerCase();
  if (raw && TAB_BY_HASH[raw]) return TAB_BY_HASH[raw];
  return "habilitations";
}

function TabFallback() {
  return (
    <div className="flex min-h-[240px] items-center justify-center rounded-lg border border-dashed bg-muted/20">
      <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
    </div>
  );
}

function formationEnrollmentStatusBadge(status: string) {
  const s = status.toLowerCase();
  const cfg: Record<string, { label: string; className: string }> = {
    planned: { label: "Planifié", className: "bg-blue-600 text-white hover:bg-blue-600" },
    in_progress: { label: "En cours", className: "bg-orange-500 text-white hover:bg-orange-500" },
    completed: { label: "Terminé", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    cancelled: { label: "Annulé", className: "bg-muted text-muted-foreground" },
    demande_salarie: {
      label: "En attente manager",
      className: "bg-amber-400 text-amber-950 hover:bg-amber-400",
    },
    approuve_manager: {
      label: "En attente RH",
      className: "bg-sky-600 text-white hover:bg-sky-600",
    },
    approuve_rh: { label: "Inscrit", className: "bg-emerald-600 text-white hover:bg-emerald-600" },
    rejete_manager: {
      label: "Refusé manager",
      className: "bg-red-600 text-white hover:bg-red-600",
    },
    rejete_rh: { label: "Refusé RH", className: "bg-red-600 text-white hover:bg-red-600" },
  };
  const x = cfg[s] ?? { label: status, className: "bg-muted text-muted-foreground" };
  return <Badge className={x.className}>{x.label}</Badge>;
}

function fmtDateTime(s?: string | null) {
  if (!s) return "—";
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("fr-FR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function FormationEvaluationsRhSection() {
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";

  const isRhLike =
    Boolean(user?.is_super_admin) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const q = useQuery({
    queryKey: ["formation-evaluations-summary", companyId],
    queryFn: () => getEvaluationsSummary(companyId),
    enabled: Boolean(companyId) && isRhLike,
  });

  if (!isRhLike) {
    return null;
  }

  const rows = [...(q.data ?? [])].sort((a, b) => b.nb_evaluations - a.nb_evaluations);

  return (
    <section className="space-y-3 border-t pt-8">
      <div>
        <h2 className="text-lg font-semibold">Évaluations formations</h2>
        <p className="text-sm text-muted-foreground">
          Synthèse des notes laissées par les collaborateurs après leurs formations.
        </p>
      </div>
      {q.isLoading ? (
        <div className="space-y-2">
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      ) : q.isError ? (
        <p className="text-sm text-destructive">Impossible de charger les statistiques d&apos;évaluation.</p>
      ) : rows.length === 0 ? (
        <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
          Aucune évaluation enregistrée pour le moment.
        </p>
      ) : (
        <div className="overflow-x-auto rounded-md border w-full">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Formation</TableHead>
                <TableHead className="text-right">Nb évaluations</TableHead>
                <TableHead>Note moyenne</TableHead>
                <TableHead className="min-w-0 max-w-[280px]">Distribution (1–5)</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row: EvaluationSummary) => {
                const dist = row.ratings_distribution ?? {};
                const counts = [1, 2, 3, 4, 5].map((n) => dist[String(n)] ?? 0);
                const maxC = Math.max(1, ...counts);
                return (
                  <TableRow key={row.training_id}>
                    <TableCell className="font-medium">{row.training_title}</TableCell>
                    <TableCell className="text-right tabular-nums">{row.nb_evaluations}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <span className="flex">
                          {[1, 2, 3, 4, 5].map((i) => (
                            <span
                              key={i}
                              className={
                                i <= Math.round(row.avg_rating)
                                  ? "text-amber-500"
                                  : "text-muted-foreground/25"
                              }
                            >
                              ★
                            </span>
                          ))}
                        </span>
                        <span className="text-sm font-medium tabular-nums text-foreground">
                          {row.avg_rating.toFixed(1)}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1">
                        {[1, 2, 3, 4, 5].map((note) => {
                          const c = dist[String(note)] ?? 0;
                          const pct = maxC > 0 ? Math.round((c / maxC) * 100) : 0;
                          return (
                            <div key={note} className="flex items-center gap-2 text-xs">
                              <span className="w-3 tabular-nums text-muted-foreground">{note}</span>
                              <div className="h-2 min-w-0 flex-1 overflow-hidden rounded bg-muted">
                                <div
                                  className="h-full rounded-sm bg-primary/80 transition-all"
                                  style={{ width: `${pct}%` }}
                                />
                              </div>
                              <span className="w-6 text-right tabular-nums text-muted-foreground">{c}</span>
                            </div>
                          );
                        })}
                      </div>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}
    </section>
  );
}

function FormationDemandesPanel() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";

  const isRhLike =
    Boolean(user?.is_super_admin) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const pendingMgrQ = useQuery({
    queryKey: ["formation-demandes", "pending-manager", companyId],
    queryFn: () => getPendingManagerApproval(companyId),
    enabled: Boolean(companyId),
  });

  const pendingRhQ = useQuery({
    queryKey: ["formation-demandes", "pending-rh", companyId],
    queryFn: () => getPendingRHApproval(companyId),
    enabled: Boolean(companyId) && isRhLike,
  });

  const [mgrReject, setMgrReject] = useState<TrainingEnrollment | null>(null);
  const [mgrRejectReason, setMgrRejectReason] = useState("");
  const [rhDialog, setRhDialog] = useState<TrainingEnrollment | null>(null);
  const [rhPlannedStart, setRhPlannedStart] = useState("");
  const [rhPlannedEnd, setRhPlannedEnd] = useState("");
  const [rhReject, setRhReject] = useState<TrainingEnrollment | null>(null);
  const [rhRejectReason, setRhRejectReason] = useState("");

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["formation-demandes"] });
  };

  const mgrApproveMut = useMutation({
    mutationFn: async ({
      row,
      approved,
      reason,
    }: {
      row: TrainingEnrollment;
      approved: boolean;
      reason?: string;
    }) => managerApprove(row.id, companyId, { approved, rejection_reason: reason }),
    onSuccess: () => {
      toast({ title: "Décision enregistrée" });
      setMgrReject(null);
      setMgrRejectReason("");
      invalidate();
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Action impossible.";
      toast({ title: "Erreur", description: String(detail), variant: "destructive" });
    },
  });

  const rhApproveMut = useMutation({
    mutationFn: async ({
      row,
      approved,
      reason,
      start,
      end,
    }: {
      row: TrainingEnrollment;
      approved: boolean;
      reason?: string;
      start?: string;
      end?: string;
    }) =>
      rhApprove(row.id, companyId, {
        approved,
        rejection_reason: reason,
        planned_start_date: start || undefined,
        planned_end_date: end || undefined,
      }),
    onSuccess: () => {
      toast({ title: "Décision enregistrée" });
      setRhDialog(null);
      setRhPlannedStart("");
      setRhPlannedEnd("");
      setRhReject(null);
      setRhRejectReason("");
      invalidate();
    },
    onError: (err: unknown) => {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "Action impossible.";
      toast({ title: "Erreur", description: String(detail), variant: "destructive" });
    },
  });

  const mgrRows = pendingMgrQ.data ?? [];
  const rhRows = pendingRhQ.data ?? [];

  return (
    <div className="space-y-10">
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">En attente validation manager</h2>
        <p className="text-sm text-muted-foreground">
          Les responsables d&apos;équipe et la RH peuvent valider ou refuser à ce stade.
        </p>
        {pendingMgrQ.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : pendingMgrQ.isError ? (
          <p className="text-sm text-destructive">Impossible de charger les demandes.</p>
        ) : mgrRows.length === 0 ? (
          <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
            Aucune demande en attente de validation manager.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-md border w-full">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Formation</TableHead>
                  <TableHead>Date demande</TableHead>
                  <TableHead>Motivation</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {mgrRows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.employee_name ?? "—"}</TableCell>
                    <TableCell>{row.training_title ?? "—"}</TableCell>
                    <TableCell>{fmtDateTime(row.created_at)}</TableCell>
                    <TableCell className="max-w-[220px] truncate text-muted-foreground" title={row.notes ?? ""}>
                      {row.notes?.replace(/\nFin prévue :.*$/s, "").trim() || "—"}
                    </TableCell>
                    <TableCell>{formationEnrollmentStatusBadge(row.status)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          variant="default"
                          disabled={mgrApproveMut.isPending}
                          onClick={() => mgrApproveMut.mutate({ row, approved: true })}
                        >
                          Approuver
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={mgrApproveMut.isPending}
                          onClick={() => {
                            setMgrReject(row);
                            setMgrRejectReason("");
                          }}
                        >
                          Refuser
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">En attente validation RH</h2>
        {!isRhLike ? (
          <p className="text-sm text-muted-foreground">
            Connectez-vous avec un compte RH pour traiter cette file.
          </p>
        ) : pendingRhQ.isLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : pendingRhQ.isError ? (
          <p className="text-sm text-destructive">Impossible de charger les demandes RH.</p>
        ) : rhRows.length === 0 ? (
          <p className="rounded-md border border-dashed py-8 text-center text-sm text-muted-foreground">
            Aucune demande en attente de validation RH.
          </p>
        ) : (
          <div className="overflow-x-auto rounded-md border w-full">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Salarié</TableHead>
                  <TableHead>Formation</TableHead>
                  <TableHead>Date demande</TableHead>
                  <TableHead>Approuvé par</TableHead>
                  <TableHead>Statut</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rhRows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="font-medium">{row.employee_name ?? "—"}</TableCell>
                    <TableCell>{row.training_title ?? "—"}</TableCell>
                    <TableCell>{fmtDateTime(row.created_at)}</TableCell>
                    <TableCell>{row.manager_display_name ?? "—"}</TableCell>
                    <TableCell>{formationEnrollmentStatusBadge(row.status)}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-2">
                        <Button
                          size="sm"
                          disabled={rhApproveMut.isPending}
                          onClick={() => {
                            setRhDialog(row);
                            setRhPlannedStart(row.planned_date?.slice(0, 10) ?? "");
                            setRhPlannedEnd("");
                          }}
                        >
                          Approuver
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={rhApproveMut.isPending}
                          onClick={() => {
                            setRhReject(row);
                            setRhRejectReason("");
                          }}
                        >
                          Refuser
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>

      <AlertDialog open={!!mgrReject} onOpenChange={(o) => !o && setMgrReject(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Refus manager</AlertDialogTitle>
          </AlertDialogHeader>
          <Textarea
            placeholder="Motif du refus (optionnel)"
            value={mgrRejectReason}
            onChange={(e) => setMgrRejectReason(e.target.value)}
            rows={3}
          />
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                if (mgrReject) {
                  mgrApproveMut.mutate({
                    row: mgrReject,
                    approved: false,
                    reason: mgrRejectReason.trim() || undefined,
                  });
                }
              }}
            >
              Confirmer le refus
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <Dialog open={!!rhDialog} onOpenChange={(o) => !o && setRhDialog(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Valider l&apos;inscription (RH)</DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground">
              Formation : <span className="font-medium text-foreground">{rhDialog?.training_title}</span>
            </p>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Date de début prévue</label>
              <Input
                type="date"
                value={rhPlannedStart}
                onChange={(e) => setRhPlannedStart(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Date de fin prévue (optionnel)</label>
              <Input type="date" value={rhPlannedEnd} onChange={(e) => setRhPlannedEnd(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setRhDialog(null)}>
              Annuler
            </Button>
            <Button
              type="button"
              disabled={rhApproveMut.isPending}
              onClick={() => {
                if (rhDialog) {
                  rhApproveMut.mutate({
                    row: rhDialog,
                    approved: true,
                    start: rhPlannedStart.trim() || undefined,
                    end: rhPlannedEnd.trim() || undefined,
                  });
                }
              }}
            >
              Confirmer l&apos;inscription
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog open={!!rhReject} onOpenChange={(o) => !o && setRhReject(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Refus RH</AlertDialogTitle>
          </AlertDialogHeader>
          <Textarea
            placeholder="Motif du refus (optionnel)"
            value={rhRejectReason}
            onChange={(e) => setRhRejectReason(e.target.value)}
            rows={3}
          />
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                if (rhReject) {
                  rhApproveMut.mutate({
                    row: rhReject,
                    approved: false,
                    reason: rhRejectReason.trim() || undefined,
                  });
                }
              }}
            >
              Confirmer le refus
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function FormationPage() {
  const navigate = useNavigate();
  const [tab, setTab] = useState<FormationTabId>(() => parseHashTab());

  const certCountsQuery = useQuery({
    queryKey: ["formation-page", "cert-dashboard-counts"],
    queryFn: () => getDashboardCounts(),
  });
  const overdueQuery = useQuery({
    queryKey: ["formation-page", "legal-overdue-count"],
    queryFn: () => getOverdueCount(),
  });

  const expired = certCountsQuery.data?.expired ?? 0;
  const expiring = certCountsQuery.data?.expiring ?? 0;
  const overdue = overdueQuery.data?.count ?? 0;

  const syncTabFromLocation = useCallback(() => {
    setTab(parseHashTab());
  }, []);

  useEffect(() => {
    syncTabFromLocation();
  }, [syncTabFromLocation]);

  useEffect(() => {
    window.addEventListener("hashchange", syncTabFromLocation);
    return () => window.removeEventListener("hashchange", syncTabFromLocation);
  }, [syncTabFromLocation]);

  const handleTabChange = (value: string) => {
    const next = value as FormationTabId;
    if (!TAB_IDS.includes(next)) return;
    setTab(next);
    const h = HASH_BY_TAB[next];
    navigate({ pathname: "/formation", hash: h }, { replace: true });
  };

  const habilitationBadges = useMemo(() => {
    if (expired > 0) {
      return <Badge className="ml-1 border-0 bg-red-600 px-1.5 text-[10px] text-white">{expired}</Badge>;
    }
    if (expiring > 0) {
      return <Badge className="ml-1 border-0 bg-orange-500 px-1.5 text-[10px] text-white">{expiring}</Badge>;
    }
    return null;
  }, [expired, expiring]);

  const obligationsBadge =
    overdue > 0 ? (
      <Badge className="ml-1 border-0 bg-red-600 px-1.5 text-[10px] text-white">{overdue}</Badge>
    ) : null;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Formation &amp; Talents</h1>
        <p className="mt-2 text-muted-foreground">
          Entretiens, trames, objectifs, habilitations, catalogue, budget, obligations légales et compétences.
        </p>
      </div>

      <Tabs value={tab} onValueChange={handleTabChange} className="w-full">
        <TabsList className="mb-4 flex h-auto w-full flex-wrap justify-start gap-1">
          <TabsTrigger value="entretiens">Entretiens</TabsTrigger>
          <TabsTrigger value="trames">Trames</TabsTrigger>
          <TabsTrigger value="objectifs">Objectifs &amp; KPI</TabsTrigger>
          <TabsTrigger value="habilitations" className="gap-0">
            <span className="inline-flex items-center">
              Habilitations
              {habilitationBadges}
            </span>
          </TabsTrigger>
          <TabsTrigger value="catalogue">Catalogue</TabsTrigger>
          <TabsTrigger value="budget">Budget</TabsTrigger>
          <TabsTrigger value="obligations" className="gap-0">
            <span className="inline-flex items-center">
              Obligations légales
              {obligationsBadge}
            </span>
          </TabsTrigger>
          <TabsTrigger value="competences">Compétences</TabsTrigger>
          <TabsTrigger value="demandes">Demandes en attente</TabsTrigger>
        </TabsList>

        <div className="mt-0 min-h-[200px]">
          {tab === "entretiens" && (
            <Suspense fallback={<TabFallback />}>
              <LazyAnnualReviews />
            </Suspense>
          )}
          {tab === "trames" && (
            <Suspense fallback={<TabFallback />}>
              <LazyInterviewTemplatesTab />
            </Suspense>
          )}
          {tab === "objectifs" && (
            <Suspense fallback={<TabFallback />}>
              <LazyObjectivesTab />
            </Suspense>
          )}
          {tab === "habilitations" && (
            <Suspense fallback={<TabFallback />}>
              <LazyHabilitationsTab />
            </Suspense>
          )}
          {tab === "catalogue" && (
            <div className="space-y-10">
              <Suspense fallback={<TabFallback />}>
                <LazyCatalogueTab />
              </Suspense>
              <FormationEvaluationsRhSection />
            </div>
          )}
          {tab === "budget" && (
            <Suspense fallback={<TabFallback />}>
              <LazyBudgetTab />
            </Suspense>
          )}
          {tab === "obligations" && (
            <Suspense fallback={<TabFallback />}>
              <LazyObligationsLegalesTab />
            </Suspense>
          )}
          {tab === "competences" && (
            <Suspense fallback={<TabFallback />}>
              <LazyCompetencesTab />
            </Suspense>
          )}
          {tab === "demandes" && <FormationDemandesPanel />}
        </div>
      </Tabs>
    </div>
  );
}
