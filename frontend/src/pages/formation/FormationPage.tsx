// Page RH unifiée Pack Talent — /formation (+ hash par onglet)

import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { getEvaluationsSummary, type EvaluationSummary } from "@/api/training";
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
  | "competences";

const TAB_IDS: FormationTabId[] = [
  "entretiens",
  "trames",
  "objectifs",
  "habilitations",
  "catalogue",
  "budget",
  "obligations",
  "competences",
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
        </div>
      </Tabs>
    </div>
  );
}
