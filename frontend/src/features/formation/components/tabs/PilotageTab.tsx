import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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
import { useCompany } from "@/contexts/CompanyContext";
import { getDashboardCounts, getEmployeeCertifications } from "@/api/certifications";
import { getOverdueCount, getAllStatus } from "@/api/legalObligations";
import { getBudget, type TrainingBudgetAlertLevel } from "@/api/trainingBudget";
import { getAchievementRate } from "@/api/objectives";
import { getAllAnnualReviews } from "@/api/annualReviews";
import { AnnualReviewBadge } from "@/components/AnnualReviewBadge";
import type { AnnualReviewStatus } from "@/api/annualReviews";
import { cn } from "@/lib/utils";

const MAX_TODO = 10;

const ACTIVE_REVIEW_STATUSES = new Set([
  "planifie",
  "en_attente_acceptation",
  "accepte",
]);

type TodoRow = {
  id: string;
  kind: "habilitation" | "obligation" | "entretien";
  label: string;
  detail: string;
  severity: "red" | "orange" | "blue";
  navigateTo: { hash: string; search?: string };
  reviewStatus?: AnnualReviewStatus;
};

function countBadgeClass(n: number, tone: "red" | "orange") {
  if (n <= 0) return "bg-muted text-muted-foreground";
  return tone === "red" ? "bg-red-600 text-white" : "bg-orange-500 text-white";
}

function budgetGaugeFillClass(level: TrainingBudgetAlertLevel) {
  if (level === "critical") return "bg-red-500";
  if (level === "warning") return "bg-orange-500";
  return "bg-emerald-500";
}

function KpiLoader() {
  return (
    <div className="flex min-h-[48px] items-center justify-center">
      <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
    </div>
  );
}

export default function PilotageTab() {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const year = new Date().getFullYear();

  const certsQuery = useQuery({
    queryKey: ["formation-pilotage", "cert-counts"],
    queryFn: getDashboardCounts,
    enabled: Boolean(companyId),
  });
  const certsListQuery = useQuery({
    queryKey: ["formation-pilotage", "cert-list"],
    queryFn: () => getEmployeeCertifications({ include_archived: false }),
    enabled: Boolean(companyId),
  });
  const overdueQuery = useQuery({
    queryKey: ["formation-pilotage", "overdue"],
    queryFn: getOverdueCount,
    enabled: Boolean(companyId),
  });
  const legalQuery = useQuery({
    queryKey: ["formation-pilotage", "legal-all"],
    queryFn: () => getAllStatus("overdue"),
    enabled: Boolean(companyId),
  });
  const budgetQuery = useQuery({
    queryKey: ["formation-pilotage", "budget", year],
    queryFn: () => getBudget(year),
    enabled: Boolean(companyId),
    retry: false,
  });
  const achievementQuery = useQuery({
    queryKey: ["formation-pilotage", "achievement", year],
    queryFn: () => getAchievementRate(year),
    enabled: Boolean(companyId),
  });
  const reviewsQuery = useQuery({
    queryKey: ["formation-pilotage", "reviews", companyId],
    queryFn: async () => {
      const res = await getAllAnnualReviews({});
      return res.data;
    },
    enabled: Boolean(companyId),
  });

  const expired = certsQuery.data?.expired ?? 0;
  const expiring = certsQuery.data?.expiring ?? 0;
  const overdue = overdueQuery.data?.count ?? 0;
  const pct =
    budgetQuery.data != null
      ? Math.min(100, Math.max(0, budgetQuery.data.consumption_pct))
      : null;
  const alertLevel = budgetQuery.data?.alert_level ?? "none";
  const rate = achievementQuery.data?.rate ?? null;

  const rateColor =
    rate == null
      ? "text-muted-foreground"
      : rate >= 80
        ? "text-emerald-600"
        : rate >= 50
          ? "text-orange-600"
          : "text-red-600";

  const todoRows = useMemo(() => {
    const items: TodoRow[] = [];

    for (const c of certsListQuery.data ?? []) {
      if (c.computed_status !== "expired" && c.computed_status !== "expiring_soon") continue;
      items.push({
        id: `cert-${c.id}`,
        kind: "habilitation",
        label: c.employee_name ?? "Collaborateur",
        detail: `${c.certification_ref?.name ?? "Habilitation"} — ${
          c.computed_status === "expired" ? "Expirée" : "Expire bientôt"
        }`,
        severity: c.computed_status === "expired" ? "red" : "orange",
        navigateTo: { hash: "conformite", search: "sub=habilitations" },
      });
    }

    for (const row of legalQuery.data ?? []) {
      if (row.professional_interview_status !== "overdue") continue;
      items.push({
        id: `legal-${row.employee_id}`,
        kind: "obligation",
        label: row.employee_name,
        detail: "Entretien professionnel en retard",
        severity: "red",
        navigateTo: { hash: "conformite", search: "sub=obligations" },
      });
    }

    for (const r of reviewsQuery.data ?? []) {
      if (!ACTIVE_REVIEW_STATUSES.has(r.status)) continue;
      items.push({
        id: `review-${r.id}`,
        kind: "entretien",
        label: `${r.first_name} ${r.last_name}`,
        detail: `Entretien — ${r.year}`,
        severity: "blue",
        navigateTo: { hash: "entretiens" },
        reviewStatus: r.status as AnnualReviewStatus,
      });
    }

    const order = { red: 0, orange: 1, blue: 2 };
    return items.sort((a, b) => order[a.severity] - order[b.severity]).slice(0, MAX_TODO);
  }, [certsListQuery.data, legalQuery.data, reviewsQuery.data]);

  const go = (hash: string, search?: string) => {
    navigate(
      { pathname: "/formation", hash, search: search?.startsWith("?") ? search : search ? `?${search}` : "" },
      { replace: false },
    );
  };

  const todoLoading =
    certsListQuery.isLoading || legalQuery.isLoading || reviewsQuery.isLoading;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold">Indicateurs</h2>
        <p className="text-sm text-muted-foreground">Cliquez sur une carte pour ouvrir le détail.</p>
      </div>

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <button
          type="button"
          onClick={() => go("conformite", "sub=habilitations")}
          className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
        >
          <span className="text-xs font-medium text-muted-foreground">Habilitations expirées</span>
          {certsQuery.isLoading ? (
            <KpiLoader />
          ) : (
            <Badge className={cn("mt-2 w-fit", countBadgeClass(expired, "red"))}>{expired}</Badge>
          )}
        </button>

        <button
          type="button"
          onClick={() => go("conformite", "sub=habilitations")}
          className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
        >
          <span className="text-xs font-medium text-muted-foreground">Habilitations à échéance</span>
          {certsQuery.isLoading ? (
            <KpiLoader />
          ) : (
            <Badge className={cn("mt-2 w-fit", countBadgeClass(expiring, "orange"))}>{expiring}</Badge>
          )}
        </button>

        <button
          type="button"
          onClick={() => go("formations", "sub=budget")}
          className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
        >
          <span className="text-xs font-medium text-muted-foreground">Budget formation consommé</span>
          {budgetQuery.isLoading ? (
            <KpiLoader />
          ) : pct == null ? (
            <p className="mt-3 text-sm text-muted-foreground">—</p>
          ) : (
            <div className="mt-3 space-y-1">
              <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full transition-all", budgetGaugeFillClass(alertLevel))}
                  style={{ width: `${pct}%` }}
                />
              </div>
              <p className="text-xs tabular-nums text-muted-foreground">{pct.toFixed(0)} %</p>
            </div>
          )}
        </button>

        <button
          type="button"
          onClick={() => go("conformite", "sub=obligations")}
          className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
        >
          <span className="text-xs font-medium text-muted-foreground">Retard entretien pro.</span>
          {overdueQuery.isLoading ? (
            <KpiLoader />
          ) : (
            <Badge className={cn("mt-2 w-fit", countBadgeClass(overdue, "red"))}>{overdue}</Badge>
          )}
        </button>

        <button
          type="button"
          onClick={() => go("developpement", "sub=objectifs")}
          className="flex flex-col rounded-lg border bg-background p-3 text-left transition-colors hover:bg-muted/60"
        >
          <span className="text-xs font-medium text-muted-foreground">Taux d&apos;atteinte objectifs</span>
          {achievementQuery.isLoading ? (
            <KpiLoader />
          ) : (
            <p className={cn("mt-3 text-2xl font-bold tabular-nums", rateColor)}>
              {rate == null ? "—" : `${rate.toFixed(0)} %`}
            </p>
          )}
        </button>
      </div>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold">À traiter</h2>
        {todoLoading ? (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        ) : todoRows.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="py-10 text-center text-sm text-muted-foreground">
              Aucune alerte prioritaire pour le moment.
            </CardContent>
          </Card>
        ) : (
          <div className="rounded-md border overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Collaborateur</TableHead>
                  <TableHead>Détail</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {todoRows.map((row) => (
                  <TableRow
                    key={row.id}
                    className="cursor-pointer hover:bg-muted/50"
                    onClick={() => {
                      if (row.kind === "entretien") {
                        const reviewId = row.id.replace("review-", "");
                        navigate(`/annual-reviews/${reviewId}`, {
                          state: { fromFormationHub: true },
                        });
                        return;
                      }
                      go(row.navigateTo.hash, row.navigateTo.search);
                    }}
                  >
                    <TableCell className="text-muted-foreground text-sm">
                      {row.kind === "habilitation"
                        ? "Habilitation"
                        : row.kind === "obligation"
                          ? "Obligation légale"
                          : "Entretien"}
                    </TableCell>
                    <TableCell className="font-medium">{row.label}</TableCell>
                    <TableCell className="text-muted-foreground">{row.detail}</TableCell>
                    <TableCell className="text-right">
                      {row.kind === "entretien" && row.reviewStatus ? (
                        <AnnualReviewBadge status={row.reviewStatus} compact />
                      ) : row.kind !== "entretien" ? (
                        <Badge
                          className={cn(
                            "border-0",
                            row.severity === "red"
                              ? "bg-red-600 text-white"
                              : row.severity === "orange"
                                ? "bg-orange-500 text-white"
                                : "bg-blue-600 text-white",
                          )}
                        >
                          {row.severity === "red" ? "Urgent" : row.severity === "orange" ? "Échéance" : "Suivi"}
                        </Badge>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </section>
    </div>
  );
}
