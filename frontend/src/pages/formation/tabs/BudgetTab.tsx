// Budget formation : enveloppe, consommation, alertes (Pack Talent T7)

import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2 } from "lucide-react";
import axios from "axios";

import {
  getAllBudgets,
  getBudget,
  saveBudget,
  type TrainingBudgetWithConsumption,
} from "@/api/trainingBudget";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useToast } from "@/components/ui/use-toast";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { useViewOptional } from "@/contexts/ViewContext";
import { cn } from "@/lib/utils";

function eur(n: number) {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(n);
}

function pct(n: number) {
  return `${n.toFixed(1)} %`;
}

function gaugeFillClass(
  consumptionPct: number,
  t1: number,
  t2: number,
): "green" | "orange" | "red" {
  if (consumptionPct >= t2) return "red";
  if (consumptionPct >= t1) return "orange";
  return "green";
}

function pctCellClass(level: string) {
  if (level === "critical") return "font-medium text-red-600";
  if (level === "warning") return "font-medium text-amber-600";
  return "text-emerald-600";
}

export default function BudgetTab() {
  const { toast } = useToast();
  const qc = useQueryClient();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const viewOpt = useViewOptional();

  const isRh =
    Boolean(user?.is_super_admin) ||
    activeCompany?.role === "admin" ||
    activeCompany?.role === "rh" ||
    activeCompany?.role === "collaborateur_rh";

  const showRhActions = Boolean(
    isRh && !(viewOpt?.isCollaborateurRh && viewOpt.viewMode === "collaborateur"),
  );

  const currentYear = new Date().getFullYear();

  const [env, setEnv] = useState("");
  const [th1, setTh1] = useState("70");
  const [th2, setTh2] = useState("90");

  const companyKey = activeCompany?.company_id ?? "none";

  const budgetQuery = useQuery({
    queryKey: ["training-budget", companyKey, currentYear],
    queryFn: () => getBudget(currentYear),
    retry: false,
    enabled: showRhActions && Boolean(activeCompany),
    throwOnError: false,
  });

  const allQuery = useQuery({
    queryKey: ["training-budget", "all", companyKey],
    queryFn: () => getAllBudgets(),
    enabled: showRhActions && Boolean(activeCompany),
  });

  useEffect(() => {
    setEnv("");
    setTh1("70");
    setTh2("90");
  }, [companyKey]);

  useEffect(() => {
    if (!budgetQuery.data) return;
    setEnv(String(budgetQuery.data.global_envelope));
    setTh1(String(budgetQuery.data.alert_threshold_1));
    setTh2(String(budgetQuery.data.alert_threshold_2));
  }, [budgetQuery.data]);

  const saveMut = useMutation({
    mutationFn: async () => {
      const g = parseFloat(env.replace(",", "."));
      const a1 = parseFloat(th1.replace(",", "."));
      const a2 = parseFloat(th2.replace(",", "."));
      if (Number.isNaN(g) || g <= 0) throw new Error("Enveloppe invalide.");
      if (Number.isNaN(a1) || Number.isNaN(a2)) throw new Error("Seuils invalides.");
      return saveBudget(currentYear, {
        global_envelope: g,
        alert_threshold_1: a1,
        alert_threshold_2: a2,
        service_breakdown: {},
      });
    },
    onSuccess: () => {
      toast({ title: "Budget enregistré" });
      void qc.invalidateQueries({ queryKey: ["training-budget"] });
    },
    onError: (e: unknown) => {
      const msg = e instanceof Error ? e.message : "Erreur";
      toast({ title: "Échec", description: msg, variant: "destructive" });
    },
  });

  const notFound =
    budgetQuery.isFetched &&
    !budgetQuery.isLoading &&
    (budgetQuery.isError || !budgetQuery.data) &&
    axios.isAxiosError(budgetQuery.error) &&
    budgetQuery.error.response?.status === 404;

  const errOther =
    budgetQuery.isError &&
    (!axios.isAxiosError(budgetQuery.error) || budgetQuery.error.response?.status !== 404);

  const gaugeData = budgetQuery.data;
  const fill = gaugeData
    ? gaugeFillClass(
        gaugeData.consumption_pct,
        gaugeData.alert_threshold_1,
        gaugeData.alert_threshold_2,
      )
    : "green";

  const fillBg =
    fill === "red"
      ? "bg-red-500"
      : fill === "orange"
        ? "bg-amber-500"
        : "bg-emerald-500";

  if (!showRhActions) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Budget formation</CardTitle>
          <CardDescription>Cette section est réservée aux équipes RH.</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <div className="space-y-8">
      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Budget {currentYear}</h2>

        {budgetQuery.isLoading && (
          <Card>
            <CardContent className="space-y-4 pt-6">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-10 w-full" />
              <Skeleton className="h-24 w-full" />
            </CardContent>
          </Card>
        )}

        {errOther && (
          <Card className="border-destructive/50">
            <CardContent className="pt-6 text-sm text-destructive">
              Impossible de charger le budget. Réessayez plus tard.
            </CardContent>
          </Card>
        )}

        {notFound && !budgetQuery.isLoading && (
          <Card className="border-dashed">
            <CardHeader>
              <CardTitle className="text-base">Aucun budget défini</CardTitle>
              <CardDescription>
                Définissez une enveloppe globale pour {currentYear} afin d’afficher la jauge et les
                alertes.
              </CardDescription>
            </CardHeader>
          </Card>
        )}

        {gaugeData && !budgetQuery.isLoading && (
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-base">Suivi de consommation</CardTitle>
              <CardDescription>
                {eur(gaugeData.consumed)} consommés sur {eur(gaugeData.global_envelope)} (
                {pct(gaugeData.consumption_pct)})
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="text-sm text-muted-foreground">Reste : {eur(gaugeData.remaining)}</div>

              <div className="h-3 w-full overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full transition-all", fillBg)}
                  style={{
                    width: `${Math.min(100, Math.max(0, gaugeData.consumption_pct))}%`,
                  }}
                />
              </div>

              {gaugeData.alert_level === "warning" && (
                <div className="flex items-start gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-950 dark:text-amber-100">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    {pct(gaugeData.consumption_pct)} du budget formation consommé. Surveillez les
                    inscriptions à venir.
                  </span>
                </div>
              )}

              {gaugeData.alert_level === "critical" && (
                <div className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-950 dark:text-red-100">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    Alerte : {pct(gaugeData.consumption_pct)} du budget formation consommé. Vérifiez
                    les inscriptions en cours.
                  </span>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Paramètres</CardTitle>
            <CardDescription>Enveloppe et seuils d’alerte (enregistrement par année).</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label htmlFor="tb-env">Enveloppe globale (€)</Label>
                <Input
                  id="tb-env"
                  type="number"
                  min={0}
                  step={100}
                  value={env}
                  onChange={(e) => setEnv(e.target.value)}
                  placeholder="Ex. 15000"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tb-t1">Seuil avertissement (%)</Label>
                <Input
                  id="tb-t1"
                  type="number"
                  min={1}
                  max={99}
                  step={1}
                  value={th1}
                  onChange={(e) => setTh1(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="tb-t2">Seuil critique (%)</Label>
                <Input
                  id="tb-t2"
                  type="number"
                  min={2}
                  max={100}
                  step={1}
                  value={th2}
                  onChange={(e) => setTh2(e.target.value)}
                />
              </div>
            </div>
            <Button type="button" onClick={() => saveMut.mutate()} disabled={saveMut.isPending}>
              {saveMut.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Enregistrer
            </Button>
          </CardContent>
        </Card>
      </section>

      <section className="space-y-4">
        <h2 className="text-lg font-semibold">Historique des budgets</h2>
        {allQuery.isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-10 w-full" />
            <Skeleton className="h-10 w-full" />
          </div>
        )}
        {allQuery.isError && (
          <p className="text-sm text-destructive">Impossible de charger l’historique.</p>
        )}
        {!allQuery.isLoading && !allQuery.isError && (allQuery.data?.length ?? 0) === 0 && (
          <Card className="border-dashed">
            <CardContent className="py-8 text-center text-sm text-muted-foreground">
              Aucun budget enregistré pour cette entreprise.
            </CardContent>
          </Card>
        )}
        {!allQuery.isLoading && (allQuery.data?.length ?? 0) > 0 && (
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Année</TableHead>
                  <TableHead>Enveloppe</TableHead>
                  <TableHead>Consommé</TableHead>
                  <TableHead>Restant</TableHead>
                  <TableHead>%</TableHead>
                  <TableHead>Alerte</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(allQuery.data ?? []).map((r: TrainingBudgetWithConsumption) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.year}</TableCell>
                    <TableCell>{eur(r.global_envelope)}</TableCell>
                    <TableCell>{eur(r.consumed)}</TableCell>
                    <TableCell>{eur(r.remaining)}</TableCell>
                    <TableCell className={pctCellClass(r.alert_level)}>{pct(r.consumption_pct)}</TableCell>
                    <TableCell>
                      {r.alert_level === "none" && (
                        <span className="text-muted-foreground">—</span>
                      )}
                      {r.alert_level === "warning" && (
                        <span className="text-amber-600">Avertissement</span>
                      )}
                      {r.alert_level === "critical" && <span className="text-red-600">Critique</span>}
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
