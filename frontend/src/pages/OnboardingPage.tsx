/**
 * Checklist d'onboarding d'un salarié (RH ou collaborateur concerné).
 */

import { useEffect, useMemo } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  completeTask,
  getMyOnboarding,
  getOnboarding,
  uncompleteTask,
  type OnboardingTask,
} from "@/api/onboarding";
import apiClient from "@/api/apiClient";
import { useAuth } from "@/contexts/AuthContext";
import { useCompany } from "@/contexts/CompanyContext";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/use-toast";
import { cn } from "@/lib/utils";
import {
  FileText,
  GraduationCap,
  Key,
  Loader2,
  Monitor,
  Users,
} from "lucide-react";

const CATEGORY_ORDER = ["administratif", "materiel", "acces", "formation", "social"] as const;

const CATEGORY_META: Record<
  string,
  { label: string; icon: typeof FileText }
> = {
  administratif: { label: "Administratif", icon: FileText },
  materiel: { label: "Matériel", icon: Monitor },
  acces: { label: "Accès", icon: Key },
  formation: { label: "Formation", icon: GraduationCap },
  social: { label: "Social", icon: Users },
};

type EmployeeHeader = {
  first_name: string;
  last_name: string;
  job_title?: string | null;
};

function groupTasksByCategory(tasks: OnboardingTask[]) {
  const map = new Map<string, OnboardingTask[]>();
  for (const t of tasks) {
    const c = (t.category || "autre").toLowerCase();
    if (!map.has(c)) map.set(c, []);
    map.get(c)!.push(t);
  }
  for (const arr of map.values()) {
    arr.sort((a, b) => a.position - b.position);
  }
  return map;
}

export function OnboardingHubPage() {
  return (
    <div className="space-y-4 p-6 max-w-2xl mx-auto">
      <h1 className="text-2xl font-bold">Onboarding</h1>
      <p className="text-muted-foreground text-sm leading-relaxed">
        Les checklists sont créées automatiquement à l&apos;embauche. Pour consulter celle d&apos;un
        salarié, ouvrez-la depuis le module Recrutement après une embauche réussie, ou depuis la
        fiche du collaborateur.
      </p>
      <Button asChild variant="default">
        <Link to="/recruitment">Aller au recrutement</Link>
      </Button>
    </div>
  );
}

export function EmployeeOnboardingRedirect() {
  const navigate = useNavigate();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";

  const { data, isPending, isError, isSuccess } = useQuery({
    queryKey: ["onboarding", "me", companyId],
    queryFn: () => getMyOnboarding(companyId),
    enabled: Boolean(companyId),
    retry: false,
  });

  useEffect(() => {
    if (isSuccess && data?.employee_id) {
      navigate(`/onboarding/${data.employee_id}`, { replace: true });
    }
  }, [isSuccess, data?.employee_id, navigate]);

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

  if (isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center p-8">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (isError || !data?.employee_id) {
    return (
      <div className="mx-auto max-w-lg p-6">
        <Card>
          <CardHeader>
            <CardTitle>Onboarding</CardTitle>
            <CardDescription>Checklist personnelle</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">
              Votre checklist d&apos;onboarding n&apos;est pas encore disponible.
            </p>
            <Button asChild variant="outline" size="sm">
              <Link to="/employee/formation">Retour à Ma formation</Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="flex min-h-[40vh] flex-col items-center justify-center gap-3 p-8 text-muted-foreground">
      <Loader2 className="h-8 w-8 animate-spin" />
      <p className="text-sm">Ouverture de votre checklist…</p>
    </div>
  );
}

export default function OnboardingPage() {
  const { employeeId } = useParams<{ employeeId: string }>();
  const { user } = useAuth();
  const { activeCompany } = useCompany();
  const companyId = activeCompany?.company_id ?? "";
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const isRh =
    user?.role === "rh" ||
    user?.role === "admin" ||
    user?.role === "collaborateur_rh";

  const {
    data: checklist,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["onboarding", employeeId, companyId],
    queryFn: () => getOnboarding(employeeId!, companyId),
    enabled: Boolean(employeeId && companyId),
    retry: false,
  });

  const { data: employee } = useQuery({
    queryKey: ["employee-header", employeeId, companyId],
    queryFn: async () => {
      const res = await apiClient.get<EmployeeHeader>(`/api/employees/${employeeId}`);
      return res.data;
    },
    enabled: Boolean(employeeId && companyId && checklist),
  });

  const byCategory = useMemo(
    () => (checklist ? groupTasksByCategory(checklist.tasks) : new Map()),
    [checklist],
  );

  const completeMut = useMutation({
    mutationFn: (taskId: string) => completeTask(employeeId!, taskId, companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", employeeId, companyId] });
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de valider la tâche.", variant: "destructive" });
    },
  });

  const uncompleteMut = useMutation({
    mutationFn: (taskId: string) => uncompleteTask(employeeId!, taskId, companyId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["onboarding", employeeId, companyId] });
    },
    onError: () => {
      toast({ title: "Erreur", description: "Impossible de réinitialiser la tâche.", variant: "destructive" });
    },
  });

  if (!employeeId) {
    return (
      <div className="p-6">
        <p className="text-muted-foreground">Identifiant salarié manquant.</p>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-6 p-6 max-w-4xl mx-auto">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-4 w-full max-w-xl" />
        <Skeleton className="h-3 w-full" />
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-32 w-full" />
          ))}
        </div>
      </div>
    );
  }

  if (isError || !checklist) {
    const ax = error as
      | { response?: { status?: number; data?: { detail?: unknown } } }
      | undefined;
    const status = ax?.response?.status;
    const detailRaw = ax?.response?.data?.detail;
    const detail = typeof detailRaw === "string" ? detailRaw : null;
    const message =
      detail ??
      (status === 404
        ? "Cette checklist n’existe pas ou vous n’y avez pas accès."
        : status === 403
          ? "Accès refusé à cette checklist."
          : "Impossible de charger la checklist (réseau ou serveur). Réessayez dans un instant.");

    return (
      <div className="p-6 max-w-xl mx-auto space-y-4">
        <h1 className="text-xl font-semibold">Onboarding</h1>
        <Card>
          <CardContent className="pt-6 space-y-4">
            <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
            <div className="flex flex-wrap gap-2">
              <Button
                type="button"
                variant="default"
                disabled={isFetching}
                onClick={() => refetch()}
              >
                {isFetching ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden />
                    Chargement…
                  </>
                ) : (
                  "Réessayer"
                )}
              </Button>
              <Button variant="outline" asChild>
                <Link to="/recruitment">Retour au recrutement</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  const fullName = employee
    ? `${employee.first_name} ${employee.last_name}`.trim()
    : "Salarié";
  const jobTitle = employee?.job_title;

  return (
    <div className="space-y-6 p-6 max-w-4xl mx-auto pb-12">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{fullName}</h1>
          {jobTitle ? (
            <p className="text-muted-foreground text-sm mt-1">{jobTitle}</p>
          ) : null}
        </div>
        {checklist.completed_at ? (
          <Badge className="bg-emerald-600 hover:bg-emerald-600 shrink-0 w-fit">Terminé 🎉</Badge>
        ) : null}
      </div>

      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="text-base">Progression globale</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <Progress value={checklist.progress_pct} className="h-2" />
          <p className="text-sm text-muted-foreground">
            {checklist.nb_completed} / {checklist.nb_total} tâches complétées (
            {checklist.progress_pct.toFixed(0)}%)
          </p>
        </CardContent>
      </Card>

      {CATEGORY_ORDER.map((cat) => {
        const tasks = byCategory.get(cat);
        if (!tasks?.length) return null;
        const meta = CATEGORY_META[cat] ?? { label: cat, icon: FileText };
        const Icon = meta.icon;
        const done = tasks.filter((t) => t.is_completed).length;
        return (
          <section key={cat} className="space-y-3">
            <h2 className="text-sm font-semibold flex items-center gap-2 border-b pb-2">
              <Icon className="h-4 w-4 text-muted-foreground" />
              {meta.label}{" "}
              <span className="text-muted-foreground font-normal">
                {done}/{tasks.length}
              </span>
            </h2>
            <ul className="space-y-2">
              {tasks.map((t) => (
                <li
                  key={t.id}
                  className="flex gap-3 rounded-lg border bg-card p-3 text-sm items-start"
                >
                  {isRh ? (
                    <Checkbox
                      checked={t.is_completed}
                      disabled={completeMut.isPending || uncompleteMut.isPending}
                      onCheckedChange={(v) => {
                        if (v === true) completeMut.mutate(t.id);
                        else if (v === false) uncompleteMut.mutate(t.id);
                      }}
                      className="mt-0.5"
                      aria-label={t.title}
                    />
                  ) : (
                    <span
                      className={cn(
                        "mt-0.5 h-4 w-4 rounded border flex-shrink-0 flex items-center justify-center text-[10px]",
                        t.is_completed ? "bg-primary text-primary-foreground border-primary" : "border-muted",
                      )}
                    >
                      {t.is_completed ? "✓" : ""}
                    </span>
                  )}
                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          "font-medium",
                          t.is_completed && "line-through text-muted-foreground",
                        )}
                      >
                        {t.title}
                      </span>
                      {t.due_days != null && t.due_days !== undefined ? (
                        <Badge variant="outline" className="text-[10px] h-5">
                          J+{t.due_days}
                        </Badge>
                      ) : null}
                    </div>
                    {t.description ? (
                      <p className="text-xs text-muted-foreground">{t.description}</p>
                    ) : null}
                    {t.is_completed && t.completed_at ? (
                      <p className="text-[11px] text-muted-foreground">
                        Complété le{" "}
                        {new Date(t.completed_at).toLocaleString("fr-FR", {
                          dateStyle: "short",
                          timeStyle: "short",
                        })}
                      </p>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}
