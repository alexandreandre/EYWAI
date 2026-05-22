/**
 * Tableau de bord RH — onboardings récents (endpoint agrégé).
 */

import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  CheckCircle2,
  ClipboardList,
  Search,
  UserPlus,
} from "lucide-react";

import { listOnboardingHub, type OnboardingHubItem } from "@/api/onboarding";
import { useCompany } from "@/contexts/CompanyContext";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import {
  formatDateFR,
  getHubStatus,
  HUB_STATUS_LABELS,
  ONBOARDING_LOOKBACK_DAYS,
  type HubStatus,
} from "@/lib/onboardingUtils";
import { cn } from "@/lib/utils";

type HubFilter = "all" | "in_progress" | "completed";

function hubStatusFromItem(item: OnboardingHubItem): HubStatus {
  return getHubStatus(item.progress_pct, item.completed_at);
}

export function OnboardingHubPage() {
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<HubFilter>("in_progress");

  const hubQuery = useQuery({
    queryKey: ["onboarding", "hub", companyId, ONBOARDING_LOOKBACK_DAYS],
    queryFn: () => listOnboardingHub(companyId, ONBOARDING_LOOKBACK_DAYS),
    enabled: Boolean(companyId),
  });

  const items = hubQuery.data?.items ?? [];
  const hubKpis = hubQuery.data?.kpis;

  const filteredItems = useMemo(() => {
    const q = search.trim().toLowerCase();
    return items.filter((item) => {
      const hubStatus = hubStatusFromItem(item);
      if (statusFilter === "in_progress" && hubStatus === "completed") return false;
      if (statusFilter === "completed" && hubStatus !== "completed") return false;
      if (!q) return true;
      const name = `${item.first_name} ${item.last_name}`.toLowerCase();
      return name.includes(q) || (item.job_title ?? "").toLowerCase().includes(q);
    });
  }, [items, search, statusFilter]);

  if (!companyId) {
    return (
      <div className="mx-auto max-w-lg p-6">
        <Card>
          <CardHeader>
            <CardTitle>Onboarding</CardTitle>
            <CardDescription>Sélectionnez une entreprise pour continuer.</CardDescription>
          </CardHeader>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6 max-w-5xl mx-auto pb-12">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Onboarding</h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl leading-relaxed">
            Suivez les intégrations des collaborateurs embauchés ces{" "}
            {hubQuery.data?.lookback_days ?? ONBOARDING_LOOKBACK_DAYS} derniers jours. Les
            checklists sont créées automatiquement à l&apos;embauche — ouvrez-les depuis le
            recrutement ou la fiche collaborateur.
          </p>
        </div>
        <Button asChild variant="outline" size="sm" className="shrink-0">
          <Link to="/recruitment">
            <UserPlus className="mr-2 h-4 w-4" />
            Recrutement
          </Link>
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Intégrations en cours</p>
                <p className="text-2xl font-bold tabular-nums">
                  {hubQuery.isPending ? "—" : (hubKpis?.in_progress ?? 0)}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-blue-100">
                <ClipboardList className="h-5 w-5 text-blue-600" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Tâches en retard</p>
                <p className="text-2xl font-bold tabular-nums text-destructive">
                  {hubQuery.isPending ? "—" : (hubKpis?.overdue_tasks ?? 0)}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-destructive/10">
                <AlertCircle className="h-5 w-5 text-destructive" />
              </div>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-muted-foreground">Terminées ce mois</p>
                <p className="text-2xl font-bold tabular-nums">
                  {hubQuery.isPending ? "—" : (hubKpis?.completed_this_month ?? 0)}
                </p>
              </div>
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-emerald-100">
                <CheckCircle2 className="h-5 w-5 text-emerald-600" />
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative max-w-sm flex-1">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Rechercher un collaborateur…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
            aria-label="Rechercher"
          />
        </div>
        <ToggleGroup
          type="single"
          value={statusFilter}
          onValueChange={(v) => {
            if (v) setStatusFilter(v as HubFilter);
          }}
          className="justify-start"
        >
          <ToggleGroupItem value="in_progress" aria-label="En cours">
            En cours
          </ToggleGroupItem>
          <ToggleGroupItem value="completed" aria-label="Terminés">
            Terminés
          </ToggleGroupItem>
          <ToggleGroupItem value="all" aria-label="Tous">
            Tous
          </ToggleGroupItem>
        </ToggleGroup>
      </div>

      {hubQuery.isError ? (
        <Card>
          <CardContent className="pt-6">
            <p className="text-sm text-muted-foreground">
              Impossible de charger le tableau de bord onboarding.
            </p>
          </CardContent>
        </Card>
      ) : hubQuery.isPending ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : filteredItems.length === 0 ? (
        <Card>
          <CardContent className="pt-6 space-y-3">
            <p className="text-sm text-muted-foreground leading-relaxed">
              Aucune intégration récente ne correspond à vos critères. Les checklists apparaissent
              après une embauche depuis le module Recrutement.
            </p>
            <Button asChild variant="default" size="sm">
              <Link to="/recruitment">Aller au recrutement</Link>
            </Button>
          </CardContent>
        </Card>
      ) : (
        <ul className="space-y-3">
          {filteredItems.map((item) => {
            const fullName = `${item.first_name} ${item.last_name}`.trim();
            const hubStatus = hubStatusFromItem(item);
            return (
              <li key={item.employee_id}>
                <Card className="transition-colors hover:bg-muted/30">
                  <CardContent className="pt-4 pb-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
                      <div className="min-w-0 flex-1 space-y-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <Link
                            to={`/onboarding/${item.employee_id}`}
                            className="font-semibold hover:underline"
                          >
                            {fullName}
                          </Link>
                          <Badge
                            variant={
                              hubStatus === "completed"
                                ? "default"
                                : hubStatus === "in_progress"
                                  ? "secondary"
                                  : "outline"
                            }
                            className={cn(
                              hubStatus === "completed" && "bg-emerald-600 hover:bg-emerald-600",
                            )}
                          >
                            {HUB_STATUS_LABELS[hubStatus]}
                          </Badge>
                          {item.nb_overdue > 0 ? (
                            <Badge variant="destructive" className="text-[10px]">
                              {item.nb_overdue} en retard
                            </Badge>
                          ) : null}
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {item.job_title ?? "—"}
                          {item.hire_date ? (
                            <>
                              {" "}
                              · Embauché le {formatDateFR(item.hire_date)}
                              {item.days_since_hire != null ? ` · J+${item.days_since_hire}` : ""}
                            </>
                          ) : null}
                        </p>
                        {item.has_checklist ? (
                          <div className="space-y-1 pt-1 max-w-md">
                            <Progress value={item.progress_pct} className="h-1.5" />
                            <p className="text-[11px] text-muted-foreground tabular-nums">
                              {item.nb_completed} / {item.nb_total} tâches (
                              {item.progress_pct.toFixed(0)}%)
                            </p>
                          </div>
                        ) : (
                          <p className="text-xs text-muted-foreground pt-1">
                            Checklist à ouvrir pour initialiser le suivi
                          </p>
                        )}
                      </div>
                      <Button asChild size="sm" variant="outline" className="shrink-0">
                        <Link to={`/onboarding/${item.employee_id}`}>Ouvrir la checklist</Link>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
